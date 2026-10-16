<?php
/**
 * Plugin Name: Draft Publisher REST Bridge
 * Description: Adds permission-checked SEO metadata, guarded draft updates, and private recovery snapshots for WP Draft Publisher.
 * Version: 1.2.0
 * Requires at least: 5.6
 * Requires PHP: 7.4
 * License: GPL-2.0-or-later
 * License URI: https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain: wp-draft-publisher-bridge
 */

if (!defined('ABSPATH')) { exit; }

define('WPDP_BRIDGE_VERSION', '1.2.0');
define('WPDP_SNAPSHOT_POST_TYPE', 'wpdp_snapshot');
define('WPDP_SNAPSHOT_LIMIT', 20);

function wpdp_bridge_register_snapshot_type() {
    register_post_type(WPDP_SNAPSHOT_POST_TYPE, array(
        'public' => false, 'show_ui' => false, 'show_in_rest' => false,
        'exclude_from_search' => true, 'supports' => array('title', 'editor', 'author'),
        'map_meta_cap' => true, 'capability_type' => 'post',
    ));
}
add_action('init', 'wpdp_bridge_register_snapshot_type', 5);

function wpdp_bridge_register_rank_math_meta() {
    foreach (array('rank_math_title', 'rank_math_description', 'rank_math_focus_keyword') as $field) {
        register_post_meta('post', $field, array(
            'type' => 'string', 'single' => true, 'show_in_rest' => true,
            'sanitize_callback' => 'sanitize_text_field',
            'auth_callback' => function ($allowed, $meta_key, $post_id) {
                return current_user_can('edit_post', $post_id);
            },
        ));
    }
}
add_action('init', 'wpdp_bridge_register_rank_math_meta', 20);

function wpdp_bridge_snapshot_payload($post_id) {
    $post = get_post($post_id);
    if (!$post || 'post' !== $post->post_type) {
        return new WP_Error('wpdp_post_not_found', __('The target post was not found.', 'wp-draft-publisher-bridge'));
    }
    return array(
        'schema_version' => 1,
        'post_id' => (int) $post_id,
        'captured_modified_gmt' => $post->post_modified_gmt,
        'title' => $post->post_title,
        'content' => $post->post_content,
        'excerpt' => $post->post_excerpt,
        'slug' => $post->post_name,
        'status' => $post->post_status,
        'featured_media' => (int) get_post_thumbnail_id($post_id),
        'categories' => array_map('intval', wp_get_post_categories($post_id)),
        'tags' => array_map('intval', wp_get_post_tags($post_id, array('fields' => 'ids'))),
        'seo' => array(
            'rank_math_title' => (string) get_post_meta($post_id, 'rank_math_title', true),
            'rank_math_description' => (string) get_post_meta($post_id, 'rank_math_description', true),
            'rank_math_focus_keyword' => (string) get_post_meta($post_id, 'rank_math_focus_keyword', true),
        ),
    );
}

function wpdp_bridge_prune_snapshots($post_id) {
    $ids = get_posts(array(
        'post_type' => WPDP_SNAPSHOT_POST_TYPE, 'post_status' => 'private',
        'posts_per_page' => -1, 'fields' => 'ids', '_wpdp_internal_query' => true,
        'meta_key' => '_wpdp_target_post', 'meta_value' => (int) $post_id,
        'orderby' => 'date ID', 'order' => 'DESC',
    ));
    foreach (array_slice($ids, WPDP_SNAPSHOT_LIMIT) as $snapshot_id) {
        wp_delete_post($snapshot_id, true);
    }
}

function wpdp_bridge_capture_snapshot($post_id, $kind = 'update') {
    $payload = wpdp_bridge_snapshot_payload($post_id);
    if (is_wp_error($payload)) { return $payload; }
    $encoded = wp_json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if (false === $encoded) {
        return new WP_Error('wpdp_snapshot_encode_failed', __('The recovery snapshot could not be encoded.', 'wp-draft-publisher-bridge'));
    }
    $operation_id = wp_generate_uuid4();
    $snapshot_id = wp_insert_post(array(
        'post_type' => WPDP_SNAPSHOT_POST_TYPE, 'post_status' => 'private',
        'post_title' => sprintf('WPDP snapshot for post %d', $post_id),
        'post_content' => wp_slash($encoded), 'post_author' => get_current_user_id(),
        'meta_input' => array(
            '_wpdp_target_post' => (int) $post_id,
            '_wpdp_operation_id' => $operation_id,
            '_wpdp_kind' => sanitize_key($kind),
        ),
    ), true);
    if (is_wp_error($snapshot_id)) { return $snapshot_id; }
    wpdp_bridge_prune_snapshots($post_id);
    return array('snapshot_id' => (int) $snapshot_id, 'operation_id' => $operation_id);
}

function wpdp_bridge_valid_snapshot_payload($payload, $post_id) {
    if (!is_array($payload)) { return false; }
    $required = array('schema_version', 'post_id', 'title', 'content', 'excerpt', 'slug', 'status', 'featured_media', 'categories', 'tags', 'seo');
    foreach ($required as $field) {
        if (!array_key_exists($field, $payload)) { return false; }
    }
    return 1 === (int) $payload['schema_version']
        && (int) $payload['post_id'] === (int) $post_id
        && 'draft' === $payload['status']
        && is_string($payload['title']) && is_string($payload['content'])
        && is_string($payload['excerpt']) && is_string($payload['slug'])
        && is_array($payload['categories']) && is_array($payload['tags']) && is_array($payload['seo']);
}

function wpdp_bridge_apply_snapshot_payload($post_id, $payload) {
    $updated = wp_update_post(array(
        'ID' => $post_id, 'post_title' => $payload['title'], 'post_content' => $payload['content'],
        'post_excerpt' => $payload['excerpt'], 'post_name' => $payload['slug'],
    ), true);
    if (is_wp_error($updated)) { return $updated; }
    $categories = wp_set_post_categories($post_id, array_map('intval', $payload['categories']), false);
    if (is_wp_error($categories)) { return $categories; }
    $tags = wp_set_post_tags($post_id, array_map('intval', $payload['tags']), false);
    if (is_wp_error($tags)) { return $tags; }
    $expected_thumbnail = absint($payload['featured_media']);
    $current_thumbnail = (int) get_post_thumbnail_id($post_id);
    if ($expected_thumbnail && $current_thumbnail !== $expected_thumbnail) {
        if (!set_post_thumbnail($post_id, $expected_thumbnail)) {
            return new WP_Error('wpdp_featured_media_restore_failed', __('The featured image could not be restored.', 'wp-draft-publisher-bridge'));
        }
    } elseif (!$expected_thumbnail && $current_thumbnail) {
        delete_post_thumbnail($post_id);
    }
    foreach (array('rank_math_title', 'rank_math_description', 'rank_math_focus_keyword') as $key) {
        $value = isset($payload['seo'][$key]) ? sanitize_text_field($payload['seo'][$key]) : '';
        if ('' === $value) { delete_post_meta($post_id, $key); } else { update_post_meta($post_id, $key, $value); }
    }
    clean_post_cache($post_id);
    return true;
}

function wpdp_bridge_payload_matches_post($post_id, $payload) {
    $current = wpdp_bridge_snapshot_payload($post_id);
    if (is_wp_error($current)) { return false; }
    foreach (array('title', 'content', 'excerpt', 'slug', 'status', 'featured_media') as $field) {
        if ($current[$field] !== $payload[$field]) { return false; }
    }
    foreach (array('categories', 'tags') as $field) {
        $expected = array_map('intval', $payload[$field]);
        $actual = array_map('intval', $current[$field]);
        sort($expected); sort($actual);
        if ($expected !== $actual) { return false; }
    }
    foreach ($current['seo'] as $key => $value) {
        $expected = isset($payload['seo'][$key]) ? sanitize_text_field($payload['seo'][$key]) : '';
        if ($value !== $expected) { return false; }
    }
    return true;
}

function wpdp_bridge_guard_draft_update($prepared_post, $request) {
    if ('1' !== $request->get_header('x-wpdp-draft-only')) { return $prepared_post; }
    $post_id = absint($request->get_param('id'));
    if (!$post_id) {
        return new WP_Error('wpdp_missing_post_id', __('A draft-only update requires a valid post ID.', 'wp-draft-publisher-bridge'), array('status' => 400));
    }
    if ('draft' !== get_post_status($post_id)) {
        return new WP_Error('wpdp_post_not_draft', __('The post is no longer a draft.', 'wp-draft-publisher-bridge'), array('status' => 409));
    }
    $expected = $request->get_header('x-wpdp-expected-modified-gmt');
    if ($expected) {
        $current = get_post_field('post_modified_gmt', $post_id, 'raw');
        if (!$current || !hash_equals($current, $expected)) {
            return new WP_Error('wpdp_post_changed_since_read', __('The draft changed after the agent read it. Reload and review the latest version before saving.', 'wp-draft-publisher-bridge'), array('status' => 409, 'current_modified_gmt' => $current));
        }
    }
    $snapshot = wpdp_bridge_capture_snapshot($post_id, 'update');
    if (is_wp_error($snapshot)) {
        return new WP_Error('wpdp_snapshot_failed', __('A recovery snapshot could not be created, so the update was stopped.', 'wp-draft-publisher-bridge'), array('status' => 500));
    }
    $request->set_param('_wpdp_snapshot_id', $snapshot['snapshot_id']);
    $request->set_param('_wpdp_operation_id', $snapshot['operation_id']);
    return $prepared_post;
}
add_filter('rest_pre_insert_post', 'wpdp_bridge_guard_draft_update', 10, 2);

function wpdp_bridge_add_operation_to_response($response, $post, $request) {
    $snapshot_id = absint($request->get_param('_wpdp_snapshot_id'));
    if (!$snapshot_id) { return $response; }
    $data = $response->get_data();
    $data['wpdp_snapshot_id'] = $snapshot_id;
    $data['wpdp_operation_id'] = sanitize_text_field($request->get_param('_wpdp_operation_id'));
    $response->set_data($data);
    return $response;
}
add_filter('rest_prepare_post', 'wpdp_bridge_add_operation_to_response', 10, 3);

function wpdp_bridge_snapshot_permission($request) {
    $post_id = absint($request->get_param('id'));
    return $post_id && current_user_can('edit_post', $post_id);
}

function wpdp_bridge_restore_permission($request) {
    $snapshot_id = absint($request->get_param('snapshot_id'));
    $target_id = absint(get_post_meta($snapshot_id, '_wpdp_target_post', true));
    return $target_id && current_user_can('edit_post', $target_id);
}

function wpdp_bridge_list_snapshots($request) {
    $post_id = absint($request->get_param('id'));
    $snapshots = get_posts(array(
        'post_type' => WPDP_SNAPSHOT_POST_TYPE, 'post_status' => 'private',
        'posts_per_page' => WPDP_SNAPSHOT_LIMIT, 'meta_key' => '_wpdp_target_post',
        'meta_value' => $post_id, 'orderby' => 'date ID', 'order' => 'DESC',
    ));
    $items = array();
    foreach ($snapshots as $snapshot) {
        $payload = json_decode($snapshot->post_content, true);
        $items[] = array(
            'snapshot_id' => (int) $snapshot->ID,
            'operation_id' => (string) get_post_meta($snapshot->ID, '_wpdp_operation_id', true),
            'kind' => (string) get_post_meta($snapshot->ID, '_wpdp_kind', true),
            'created_gmt' => $snapshot->post_date_gmt,
            'captured_modified_gmt' => is_array($payload) && isset($payload['captured_modified_gmt']) ? $payload['captured_modified_gmt'] : null,
        );
    }
    return rest_ensure_response(array('post_id' => $post_id, 'snapshots' => $items));
}

function wpdp_bridge_restore_snapshot($request) {
    $snapshot_id = absint($request->get_param('snapshot_id'));
    $snapshot = get_post($snapshot_id);
    $post_id = absint(get_post_meta($snapshot_id, '_wpdp_target_post', true));
    if (!$snapshot || WPDP_SNAPSHOT_POST_TYPE !== $snapshot->post_type || !$post_id) {
        return new WP_Error('wpdp_snapshot_not_found', __('The recovery snapshot was not found.', 'wp-draft-publisher-bridge'), array('status' => 404));
    }
    if ('draft' !== get_post_status($post_id)) {
        return new WP_Error('wpdp_post_not_draft', __('Only a draft can be restored.', 'wp-draft-publisher-bridge'), array('status' => 409));
    }
    $payload = json_decode($snapshot->post_content, true);
    if (!wpdp_bridge_valid_snapshot_payload($payload, $post_id)) {
        return new WP_Error('wpdp_snapshot_invalid', __('The recovery snapshot is invalid.', 'wp-draft-publisher-bridge'), array('status' => 409));
    }
    $recovery = wpdp_bridge_capture_snapshot($post_id, 'pre_restore');
    if (is_wp_error($recovery)) {
        return new WP_Error('wpdp_snapshot_failed', __('A recovery point for the current draft could not be created.', 'wp-draft-publisher-bridge'), array('status' => 500));
    }
    $applied = wpdp_bridge_apply_snapshot_payload($post_id, $payload);
    if (is_wp_error($applied) || !wpdp_bridge_payload_matches_post($post_id, $payload)) {
        $recovery_post = get_post($recovery['snapshot_id']);
        $recovery_payload = $recovery_post ? json_decode($recovery_post->post_content, true) : null;
        $recovered = false;
        if (wpdp_bridge_valid_snapshot_payload($recovery_payload, $post_id)) {
            $rollback = wpdp_bridge_apply_snapshot_payload($post_id, $recovery_payload);
            $recovered = !is_wp_error($rollback) && wpdp_bridge_payload_matches_post($post_id, $recovery_payload);
        }
        return new WP_Error(
            'wpdp_snapshot_restore_failed',
            $recovered
                ? __('The snapshot could not be fully restored. The previous draft was recovered.', 'wp-draft-publisher-bridge')
                : __('The snapshot and automatic recovery both failed. Review the draft before making another change.', 'wp-draft-publisher-bridge'),
            array('status' => 500, 'recovered' => $recovered)
        );
    }
    return rest_ensure_response(array(
        'ok' => true, 'post_id' => $post_id, 'restored_snapshot_id' => $snapshot_id,
        'recovery_snapshot_id' => $recovery['snapshot_id'],
        'modified_gmt' => get_post_field('post_modified_gmt', $post_id, 'raw'),
    ));
}

function wpdp_bridge_status_permission() { return current_user_can('edit_posts'); }

function wpdp_bridge_status() {
    return rest_ensure_response(array(
        'version' => WPDP_BRIDGE_VERSION, 'atomic_draft_guard' => true,
        'optimistic_locking' => true, 'snapshots' => true,
        'snapshot_limit' => WPDP_SNAPSHOT_LIMIT,
        'rank_math_meta' => array('rank_math_title', 'rank_math_description', 'rank_math_focus_keyword'),
    ));
}

function wpdp_bridge_register_routes() {
    register_rest_route('wp-draft-publisher/v1', '/status', array(
        'methods' => WP_REST_Server::READABLE, 'callback' => 'wpdp_bridge_status',
        'permission_callback' => 'wpdp_bridge_status_permission',
    ));
    register_rest_route('wp-draft-publisher/v1', '/posts/(?P<id>\d+)/snapshots', array(
        'methods' => WP_REST_Server::READABLE, 'callback' => 'wpdp_bridge_list_snapshots',
        'permission_callback' => 'wpdp_bridge_snapshot_permission',
    ));
    register_rest_route('wp-draft-publisher/v1', '/snapshots/(?P<snapshot_id>\d+)/restore', array(
        'methods' => WP_REST_Server::CREATABLE, 'callback' => 'wpdp_bridge_restore_snapshot',
        'permission_callback' => 'wpdp_bridge_restore_permission',
    ));
}
add_action('rest_api_init', 'wpdp_bridge_register_routes');

function wpdp_bridge_delete_snapshots_with_post($post_id) {
    if ('post' !== get_post_type($post_id)) { return; }
    $ids = get_posts(array(
        'post_type' => WPDP_SNAPSHOT_POST_TYPE, 'post_status' => 'private',
        'posts_per_page' => -1, 'fields' => 'ids',
        'meta_key' => '_wpdp_target_post', 'meta_value' => (int) $post_id,
    ));
    foreach ($ids as $snapshot_id) { wp_delete_post($snapshot_id, true); }
}
add_action('before_delete_post', 'wpdp_bridge_delete_snapshots_with_post');
