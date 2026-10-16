<?php
/**
 * Plugin Name: Draft Publisher REST Bridge
 * Description: Adds permission-checked SEO metadata, guarded draft updates, recovery snapshots, and privacy-safe activity records for WP Draft Publisher.
 * Version: 1.3.0
 * Requires at least: 5.6
 * Requires PHP: 7.4
 * License: GPL-2.0-or-later
 * License URI: https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain: wp-draft-publisher-bridge
 */

if (!defined('ABSPATH')) { exit; }

define('WPDP_BRIDGE_VERSION', '1.3.0');
define('WPDP_SNAPSHOT_POST_TYPE', 'wpdp_snapshot');
define('WPDP_SNAPSHOT_LIMIT', 20);
define('WPDP_ACTIVITY_POST_TYPE', 'wpdp_activity');
define('WPDP_ACTIVITY_LIMIT', 500);

function wpdp_bridge_register_snapshot_type() {
    register_post_type(WPDP_SNAPSHOT_POST_TYPE, array(
        'public' => false, 'show_ui' => false, 'show_in_rest' => false,
        'exclude_from_search' => true, 'supports' => array('title', 'editor', 'author'),
        'map_meta_cap' => true, 'capability_type' => 'post',
    ));
    register_post_type(WPDP_ACTIVITY_POST_TYPE, array(
        'public' => false, 'show_ui' => false, 'show_in_rest' => false,
        'exclude_from_search' => true, 'supports' => array('author'),
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

function wpdp_bridge_capture_snapshot($post_id, $kind = 'update', $operation_id = '') {
    $payload = wpdp_bridge_snapshot_payload($post_id);
    if (is_wp_error($payload)) { return $payload; }
    $encoded = wp_json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if (false === $encoded) {
        return new WP_Error('wpdp_snapshot_encode_failed', __('The recovery snapshot could not be encoded.', 'wp-draft-publisher-bridge'));
    }
    $operation_id = wpdp_bridge_sanitize_operation_id($operation_id);
    if (!$operation_id) { $operation_id = wp_generate_uuid4(); }
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

function wpdp_bridge_sanitize_operation_id($value) {
    $value = strtolower(sanitize_text_field((string) $value));
    return preg_match('/^[a-z0-9][a-z0-9._:-]{0,63}$/', $value) ? $value : '';
}

function wpdp_bridge_media_ids_from_request($request) {
    $raw = (string) $request->get_header('x-wpdp-media-ids');
    if ('' === $raw) { return array(); }
    return array_values(array_unique(array_filter(array_map('absint', explode(',', $raw)))));
}

function wpdp_bridge_prune_activity() {
    $ids = get_posts(array(
        'post_type' => WPDP_ACTIVITY_POST_TYPE, 'post_status' => 'private',
        'posts_per_page' => -1, 'fields' => 'ids', '_wpdp_internal_query' => true,
        'orderby' => 'date ID', 'order' => 'DESC',
    ));
    foreach (array_slice($ids, WPDP_ACTIVITY_LIMIT) as $activity_id) {
        wp_delete_post($activity_id, true);
    }
}

function wpdp_bridge_record_activity($action, $post_id, $status, $operation_id = '', $media_ids = array()) {
    $post_id = absint($post_id);
    if (!$post_id || 'post' !== get_post_type($post_id)) { return 0; }
    $activity_id = wp_insert_post(array(
        'post_type' => WPDP_ACTIVITY_POST_TYPE, 'post_status' => 'private',
        'post_author' => get_current_user_id(),
        'meta_input' => array(
            '_wpdp_action' => sanitize_key($action),
            '_wpdp_target_post' => $post_id,
            '_wpdp_status' => sanitize_key($status),
            '_wpdp_operation_id' => wpdp_bridge_sanitize_operation_id($operation_id),
            '_wpdp_media_ids' => implode(',', array_values(array_unique(array_filter(array_map('absint', $media_ids))))),
        ),
    ), true);
    if (!is_wp_error($activity_id)) { wpdp_bridge_prune_activity(); }
    return is_wp_error($activity_id) ? 0 : (int) $activity_id;
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
    $operation_id = wpdp_bridge_sanitize_operation_id($request->get_header('x-wpdp-operation-id'));
    $snapshot = wpdp_bridge_capture_snapshot($post_id, 'update', $operation_id);
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
    $operation_id = wpdp_bridge_sanitize_operation_id($request->get_param('_wpdp_operation_id'));
    if (!$operation_id) { $operation_id = wpdp_bridge_sanitize_operation_id($request->get_header('x-wpdp-operation-id')); }
    if (!$snapshot_id && !$operation_id) { return $response; }
    $data = $response->get_data();
    if ($snapshot_id) { $data['wpdp_snapshot_id'] = $snapshot_id; }
    if ($operation_id) { $data['wpdp_operation_id'] = $operation_id; }
    $response->set_data($data);
    return $response;
}
add_filter('rest_prepare_post', 'wpdp_bridge_add_operation_to_response', 10, 3);

function wpdp_bridge_log_rest_post($post, $request, $creating) {
    if ('1' !== $request->get_header('x-wpdp-agent') || 'post' !== $post->post_type) { return; }
    $operation_id = wpdp_bridge_sanitize_operation_id($request->get_header('x-wpdp-operation-id'));
    wpdp_bridge_record_activity(
        $creating ? 'create_draft' : 'update_draft',
        $post->ID,
        'success',
        $operation_id,
        wpdp_bridge_media_ids_from_request($request)
    );
}
add_action('rest_after_insert_post', 'wpdp_bridge_log_rest_post', 10, 3);

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
    $operation_id = (string) get_post_meta($snapshot_id, '_wpdp_operation_id', true);
    wpdp_bridge_record_activity('restore_snapshot', $post_id, 'success', $operation_id, array());
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
        'snapshot_limit' => WPDP_SNAPSHOT_LIMIT, 'activity_log' => true,
        'activity_limit' => WPDP_ACTIVITY_LIMIT,
        'rank_math_meta' => array('rank_math_title', 'rank_math_description', 'rank_math_focus_keyword'),
    ));
}

function wpdp_bridge_activity_permission() { return current_user_can('edit_posts'); }

function wpdp_bridge_activity_items($limit) {
    $records = get_posts(array(
        'post_type' => WPDP_ACTIVITY_POST_TYPE, 'post_status' => 'private',
        'posts_per_page' => min(100, max(1, absint($limit))),
        'orderby' => 'date ID', 'order' => 'DESC',
    ));
    $items = array();
    foreach ($records as $record) {
        $post_id = absint(get_post_meta($record->ID, '_wpdp_target_post', true));
        if (!$post_id || !current_user_can('edit_post', $post_id)) { continue; }
        $media_raw = (string) get_post_meta($record->ID, '_wpdp_media_ids', true);
        $items[] = array(
            'id' => (int) $record->ID,
            'created_gmt' => $record->post_date_gmt,
            'user_id' => (int) $record->post_author,
            'action' => (string) get_post_meta($record->ID, '_wpdp_action', true),
            'post_id' => $post_id,
            'status' => (string) get_post_meta($record->ID, '_wpdp_status', true),
            'operation_id' => (string) get_post_meta($record->ID, '_wpdp_operation_id', true),
            'media_ids' => '' === $media_raw ? array() : array_values(array_filter(array_map('absint', explode(',', $media_raw)))),
        );
    }
    return $items;
}

function wpdp_bridge_list_activity($request) {
    return rest_ensure_response(array(
        'activity' => wpdp_bridge_activity_items($request->get_param('per_page')),
        'privacy' => 'No credentials or post body content are stored.',
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
    register_rest_route('wp-draft-publisher/v1', '/activity', array(
        'methods' => WP_REST_Server::READABLE, 'callback' => 'wpdp_bridge_list_activity',
        'permission_callback' => 'wpdp_bridge_activity_permission',
        'args' => array('per_page' => array('default' => 50, 'sanitize_callback' => 'absint')),
    ));
}
add_action('rest_api_init', 'wpdp_bridge_register_routes');

function wpdp_bridge_register_activity_page() {
    add_management_page(
        __('Draft Publisher Activity', 'wp-draft-publisher-bridge'),
        __('Draft Publisher Activity', 'wp-draft-publisher-bridge'),
        'edit_posts', 'wpdp-activity', 'wpdp_bridge_render_activity_page'
    );
}
add_action('admin_menu', 'wpdp_bridge_register_activity_page');

function wpdp_bridge_render_activity_page() {
    if (!current_user_can('edit_posts')) { wp_die(esc_html__('You do not have permission to view this page.', 'wp-draft-publisher-bridge')); }
    $items = wpdp_bridge_activity_items(100);
    echo '<div class="wrap"><h1>' . esc_html__('Draft Publisher Activity', 'wp-draft-publisher-bridge') . '</h1>';
    echo '<p>' . esc_html__('This log stores operation metadata only. It never stores credentials or article body content.', 'wp-draft-publisher-bridge') . '</p>';
    echo '<table class="widefat striped"><thead><tr><th>Date (GMT)</th><th>User</th><th>Action</th><th>Post</th><th>Media IDs</th><th>Status</th><th>Operation</th></tr></thead><tbody>';
    if (!$items) { echo '<tr><td colspan="7">' . esc_html__('No activity recorded yet.', 'wp-draft-publisher-bridge') . '</td></tr>'; }
    foreach ($items as $item) {
        $user = get_userdata($item['user_id']);
        $post_link = get_edit_post_link($item['post_id']);
        echo '<tr><td>' . esc_html($item['created_gmt']) . '</td><td>' . esc_html($user ? $user->display_name : (string) $item['user_id']) . '</td><td>' . esc_html($item['action']) . '</td><td>';
        if ($post_link) { echo '<a href="' . esc_url($post_link) . '">#' . esc_html((string) $item['post_id']) . '</a>'; } else { echo '#' . esc_html((string) $item['post_id']); }
        echo '</td><td>' . esc_html(implode(', ', $item['media_ids'])) . '</td><td>' . esc_html($item['status']) . '</td><td><code>' . esc_html($item['operation_id']) . '</code></td></tr>';
    }
    echo '</tbody></table></div>';
}

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
