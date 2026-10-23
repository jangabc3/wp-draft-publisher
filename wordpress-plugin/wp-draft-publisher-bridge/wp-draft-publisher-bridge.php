<?php
/**
 * Plugin Name: Draft Publisher REST Bridge
 * Description: Adds multi-plugin SEO fields, guarded draft updates, recovery snapshots, and privacy-safe activity records for WP Draft Publisher.
 * Version: 1.6.1
 * Requires at least: 5.6
 * Requires PHP: 7.4
 * License: GPL-2.0-or-later
 * License URI: https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain: wp-draft-publisher-bridge
 */

if (!defined('ABSPATH')) { exit; }

define('WPDP_BRIDGE_VERSION', '1.6.1');
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

function wpdp_bridge_register_seo_meta() {
    $fields = array(
        'rank_math_title', 'rank_math_description', 'rank_math_focus_keyword',
        '_yoast_wpseo_title', '_yoast_wpseo_metadesc', '_yoast_wpseo_focuskw',
    );
    foreach ($fields as $field) {
        register_post_meta('post', $field, array(
            'type' => 'string', 'single' => true, 'show_in_rest' => true,
            'sanitize_callback' => 'sanitize_text_field',
            'auth_callback' => function ($allowed, $meta_key, $post_id) {
                return current_user_can('edit_post', $post_id);
            },
        ));
    }
}
add_action('init', 'wpdp_bridge_register_seo_meta', 20);

function wpdp_bridge_available_seo_providers() {
    $providers = array();
    if (defined('RANK_MATH_VERSION') || class_exists('RankMath')) { $providers[] = 'rank-math'; }
    if (defined('WPSEO_VERSION') || class_exists('WPSEO_Meta')) { $providers[] = 'yoast'; }
    if (function_exists('aioseo') || class_exists('AIOSEO\\Plugin\\Common\\Models\\Post')) { $providers[] = 'aioseo'; }
    return $providers;
}

function wpdp_bridge_active_seo_provider() {
    $providers = wpdp_bridge_available_seo_providers();
    return $providers ? $providers[0] : 'wordpress';
}

function wpdp_bridge_aioseo_model($post_id) {
    $class = 'AIOSEO\\Plugin\\Common\\Models\\Post';
    if (!class_exists($class) || !is_callable(array($class, 'getPost'))) { return null; }
    return call_user_func(array($class, 'getPost'), $post_id);
}

function wpdp_bridge_get_seo($post_id, $provider = 'auto') {
    if ('auto' === $provider) { $provider = wpdp_bridge_active_seo_provider(); }
    $result = array('provider' => $provider, 'title' => '', 'description' => '', 'focus_keyword' => '');
    if ('rank-math' === $provider) {
        $result['title'] = (string) get_post_meta($post_id, 'rank_math_title', true);
        $result['description'] = (string) get_post_meta($post_id, 'rank_math_description', true);
        $result['focus_keyword'] = (string) get_post_meta($post_id, 'rank_math_focus_keyword', true);
    } elseif ('yoast' === $provider) {
        $result['title'] = (string) get_post_meta($post_id, '_yoast_wpseo_title', true);
        $result['description'] = (string) get_post_meta($post_id, '_yoast_wpseo_metadesc', true);
        $result['focus_keyword'] = (string) get_post_meta($post_id, '_yoast_wpseo_focuskw', true);
    } elseif ('aioseo' === $provider) {
        $model = wpdp_bridge_aioseo_model($post_id);
        if ($model) {
            $result['title'] = (string) $model->title;
            $result['description'] = (string) $model->description;
            $phrases = json_decode(wp_json_encode($model->keyphrases), true);
            $result['focus_keyword'] = !empty($model->focus_keyword)
                ? (string) $model->focus_keyword
                : (isset($phrases['focus']['keyphrase']) ? (string) $phrases['focus']['keyphrase'] : '');
        }
    } else {
        $post = get_post($post_id);
        $result['provider'] = 'wordpress';
        $result['title'] = $post ? $post->post_title : '';
        $result['description'] = $post ? $post->post_excerpt : '';
    }
    $result['title_saved'] = '' !== $result['title'];
    $result['description_saved'] = '' !== $result['description'];
    $result['focus_keyword_saved'] = '' !== $result['focus_keyword'];
    return $result;
}

function wpdp_bridge_set_seo($post_id, $provider, $title, $description, $focus_keyword) {
    if ('auto' === $provider) { $provider = wpdp_bridge_active_seo_provider(); }
    if (!in_array($provider, array('rank-math', 'yoast', 'aioseo', 'wordpress'), true)) {
        return new WP_Error('wpdp_invalid_seo_provider', __('Unsupported SEO provider.', 'wp-draft-publisher-bridge'), array('status' => 400));
    }
    if ('wordpress' === $provider) { return wpdp_bridge_get_seo($post_id, 'wordpress'); }
    if (!in_array($provider, wpdp_bridge_available_seo_providers(), true)) {
        return new WP_Error('wpdp_seo_provider_unavailable', __('The requested SEO plugin is not active.', 'wp-draft-publisher-bridge'), array('status' => 409));
    }
    if ('rank-math' === $provider) {
        $keys = array('rank_math_title' => $title, 'rank_math_description' => $description, 'rank_math_focus_keyword' => $focus_keyword);
        foreach ($keys as $key => $value) { update_post_meta($post_id, $key, $value); }
    } elseif ('yoast' === $provider) {
        $keys = array('_yoast_wpseo_title' => $title, '_yoast_wpseo_metadesc' => $description, '_yoast_wpseo_focuskw' => $focus_keyword);
        foreach ($keys as $key => $value) { update_post_meta($post_id, $key, $value); }
    } else {
        $model = wpdp_bridge_aioseo_model($post_id);
        $class = 'AIOSEO\\Plugin\\Common\\Models\\Post';
        if (!$model || !is_callable(array($class, 'savePost'))) {
            return new WP_Error('wpdp_aioseo_model_unavailable', __('AIOSEO is active but its post model is unavailable.', 'wp-draft-publisher-bridge'), array('status' => 409));
        }
        $phrases = json_decode(wp_json_encode($model->keyphrases), true);
        if (!is_array($phrases)) { $phrases = array(); }
        if (!isset($phrases['focus']) || !is_array($phrases['focus'])) { $phrases['focus'] = array(); }
        if (!isset($phrases['additional']) || !is_array($phrases['additional'])) { $phrases['additional'] = array(); }
        $phrases['focus']['keyphrase'] = $focus_keyword;
        $saved = call_user_func(array($class, 'savePost'), $post_id, array(
            'title' => $title, 'description' => $description, 'keyphrases' => $phrases,
        ));
        if (false === $saved || is_string($saved)) {
            return new WP_Error('wpdp_aioseo_save_failed', __('AIOSEO rejected the SEO values.', 'wp-draft-publisher-bridge'), array('status' => 500));
        }
    }
    clean_post_cache($post_id);
    return wpdp_bridge_get_seo($post_id, $provider);
}

function wpdp_bridge_snapshot_payload($post_id) {
    $post = get_post($post_id);
    if (!$post || 'post' !== $post->post_type) {
        return new WP_Error('wpdp_post_not_found', __('The target post was not found.', 'wp-draft-publisher-bridge'));
    }
    return array(
        'schema_version' => 2,
        'post_id' => (int) $post_id,
        'captured_modified_gmt' => wpdp_bridge_rest_modified_gmt($post_id),
        'title' => $post->post_title,
        'content' => $post->post_content,
        'excerpt' => $post->post_excerpt,
        'slug' => $post->post_name,
        'status' => $post->post_status,
        'featured_media' => (int) get_post_thumbnail_id($post_id),
        'categories' => array_map('intval', wp_get_post_categories($post_id)),
        'tags' => array_map('intval', wp_get_post_tags($post_id, array('fields' => 'ids'))),
        'seo' => wpdp_bridge_get_seo($post_id, 'auto'),
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

function wpdp_bridge_rest_modified_gmt($post_id) {
    $post = get_post($post_id);
    if (!$post) { return ''; }
    $modified_gmt = $post->post_modified_gmt;
    if (!$modified_gmt || '0000-00-00 00:00:00' === $modified_gmt) {
        $modified_gmt = get_gmt_from_date($post->post_modified);
    }
    return mysql_to_rfc3339($modified_gmt);
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
    return in_array((int) $payload['schema_version'], array(1, 2), true)
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
    if (1 === (int) $payload['schema_version']) {
        foreach (array('rank_math_title', 'rank_math_description', 'rank_math_focus_keyword') as $key) {
            $value = isset($payload['seo'][$key]) ? sanitize_text_field($payload['seo'][$key]) : '';
            if ('' === $value) { delete_post_meta($post_id, $key); } else { update_post_meta($post_id, $key, $value); }
        }
    } else {
        $seo = $payload['seo'];
        $restored = wpdp_bridge_set_seo(
            $post_id,
            isset($seo['provider']) ? sanitize_key($seo['provider']) : 'auto',
            isset($seo['title']) ? sanitize_text_field($seo['title']) : '',
            isset($seo['description']) ? sanitize_text_field($seo['description']) : '',
            isset($seo['focus_keyword']) ? sanitize_text_field($seo['focus_keyword']) : ''
        );
        if (is_wp_error($restored)) { return $restored; }
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
    if (1 === (int) $payload['schema_version']) {
        foreach (array('rank_math_title', 'rank_math_description', 'rank_math_focus_keyword') as $key) {
            $expected = isset($payload['seo'][$key]) ? sanitize_text_field($payload['seo'][$key]) : '';
            if ((string) get_post_meta($post_id, $key, true) !== $expected) { return false; }
        }
    } else {
        foreach (array('provider', 'title', 'description', 'focus_keyword') as $key) {
            $expected = isset($payload['seo'][$key]) ? sanitize_text_field($payload['seo'][$key]) : '';
            if ((string) $current['seo'][$key] !== $expected) { return false; }
        }
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
        $current = wpdp_bridge_rest_modified_gmt($post_id);
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

function wpdp_bridge_seo_permission($request) {
    $post_id = absint($request->get_param('id'));
    return $post_id && current_user_can('edit_post', $post_id);
}

function wpdp_bridge_read_seo($request) {
    $post_id = absint($request->get_param('id'));
    if ('post' !== get_post_type($post_id)) {
        return new WP_Error('wpdp_post_not_found', __('The target post was not found.', 'wp-draft-publisher-bridge'), array('status' => 404));
    }
    $provider = sanitize_key((string) $request->get_param('provider'));
    return rest_ensure_response(wpdp_bridge_get_seo($post_id, $provider ? $provider : 'auto'));
}

function wpdp_bridge_write_seo($request) {
    $post_id = absint($request->get_param('id'));
    if ('draft' !== get_post_status($post_id)) {
        return new WP_Error('wpdp_post_not_draft', __('SEO can only be changed for a draft.', 'wp-draft-publisher-bridge'), array('status' => 409));
    }
    $provider = sanitize_key((string) $request->get_param('provider'));
    $saved = wpdp_bridge_set_seo(
        $post_id,
        $provider ? $provider : 'auto',
        sanitize_text_field((string) $request->get_param('title')),
        sanitize_text_field((string) $request->get_param('description')),
        sanitize_text_field((string) $request->get_param('focus_keyword'))
    );
    if (is_wp_error($saved)) { return $saved; }
    $operation_id = wpdp_bridge_sanitize_operation_id($request->get_param('operation_id'));
    wpdp_bridge_record_activity('update_seo', $post_id, 'success', $operation_id, array());
    return rest_ensure_response(array_merge(array('ok' => true), $saved));
}

function wpdp_bridge_status() {
    return rest_ensure_response(array(
        'version' => WPDP_BRIDGE_VERSION, 'atomic_draft_guard' => true,
        'optimistic_locking' => true, 'snapshots' => true,
        'snapshot_limit' => WPDP_SNAPSHOT_LIMIT, 'activity_log' => true,
        'activity_limit' => WPDP_ACTIVITY_LIMIT,
        'rank_math_meta' => array('rank_math_title', 'rank_math_description', 'rank_math_focus_keyword'),
        'seo_providers' => wpdp_bridge_available_seo_providers(),
        'active_seo_provider' => wpdp_bridge_active_seo_provider(),
        'site_name' => get_bloginfo('name'),
        'language' => get_locale(),
        'wordpress_version' => get_bloginfo('version'),
        'home_url' => home_url('/'),
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
    register_rest_route('wp-draft-publisher/v1', '/posts/(?P<id>\d+)/seo', array(
        array(
            'methods' => WP_REST_Server::READABLE, 'callback' => 'wpdp_bridge_read_seo',
            'permission_callback' => 'wpdp_bridge_seo_permission',
            'args' => array('provider' => array('default' => 'auto', 'sanitize_callback' => 'sanitize_key')),
        ),
        array(
            'methods' => WP_REST_Server::CREATABLE, 'callback' => 'wpdp_bridge_write_seo',
            'permission_callback' => 'wpdp_bridge_seo_permission',
            'args' => array(
                'provider' => array('default' => 'auto', 'sanitize_callback' => 'sanitize_key'),
                'title' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                'description' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                'focus_keyword' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                'operation_id' => array('default' => '', 'sanitize_callback' => 'sanitize_text_field'),
            ),
        ),
    ));
}
add_action('rest_api_init', 'wpdp_bridge_register_routes');

function wpdp_bridge_register_activity_page() {
    add_management_page(
        __('Draft Publisher', 'wp-draft-publisher-bridge'),
        __('Draft Publisher', 'wp-draft-publisher-bridge'),
        'edit_posts', 'wpdp-activity', 'wpdp_bridge_render_activity_page'
    );
}
add_action('admin_menu', 'wpdp_bridge_register_activity_page');

function wpdp_bridge_recent_snapshots($limit = 20) {
    $records = get_posts(array(
        'post_type' => WPDP_SNAPSHOT_POST_TYPE, 'post_status' => 'private',
        'posts_per_page' => min(50, max(1, absint($limit))),
        'orderby' => 'date ID', 'order' => 'DESC', '_wpdp_internal_query' => true,
    ));
    $items = array();
    foreach ($records as $record) {
        $post_id = absint(get_post_meta($record->ID, '_wpdp_target_post', true));
        if (!$post_id || !current_user_can('edit_post', $post_id)) { continue; }
        $items[] = array(
            'snapshot_id' => (int) $record->ID,
            'post_id' => $post_id,
            'title' => get_the_title($post_id),
            'created_gmt' => $record->post_date_gmt,
            'kind' => (string) get_post_meta($record->ID, '_wpdp_kind', true),
            'operation_id' => (string) get_post_meta($record->ID, '_wpdp_operation_id', true),
            'can_restore' => 'draft' === get_post_status($post_id),
        );
    }
    return $items;
}

function wpdp_bridge_admin_restore_snapshot() {
    if (!current_user_can('edit_posts')) { wp_die(esc_html__('You do not have permission to restore drafts.', 'wp-draft-publisher-bridge')); }
    $snapshot_id = isset($_POST['snapshot_id']) ? absint(wp_unslash($_POST['snapshot_id'])) : 0;
    check_admin_referer('wpdp_restore_snapshot_' . $snapshot_id);
    $request = new WP_REST_Request('POST');
    $request->set_param('snapshot_id', $snapshot_id);
    if (!wpdp_bridge_restore_permission($request)) {
        wp_die(esc_html__('You do not have permission to restore this draft.', 'wp-draft-publisher-bridge'));
    }
    $response = wpdp_bridge_restore_snapshot($request);
    $result = is_wp_error($response) ? 'error' : 'restored';
    $message = is_wp_error($response) ? $response->get_error_message() : __('The draft was restored and verified.', 'wp-draft-publisher-bridge');
    wp_safe_redirect(add_query_arg(array(
        'page' => 'wpdp-activity', 'tab' => 'recovery', 'wpdp_result' => $result,
        'wpdp_message' => rawurlencode($message),
    ), admin_url('tools.php')));
    exit;
}
add_action('admin_post_wpdp_restore_snapshot', 'wpdp_bridge_admin_restore_snapshot');

function wpdp_bridge_admin_status_rows() {
    $user = wp_get_current_user();
    return array(
        __('Bridge version', 'wp-draft-publisher-bridge') => WPDP_BRIDGE_VERSION,
        __('WordPress', 'wp-draft-publisher-bridge') => get_bloginfo('version'),
        __('Site language', 'wp-draft-publisher-bridge') => get_locale(),
        __('Current user', 'wp-draft-publisher-bridge') => $user->display_name,
        __('Create drafts', 'wp-draft-publisher-bridge') => current_user_can('edit_posts') ? __('Allowed', 'wp-draft-publisher-bridge') : __('Blocked', 'wp-draft-publisher-bridge'),
        __('Upload media', 'wp-draft-publisher-bridge') => current_user_can('upload_files') ? __('Allowed', 'wp-draft-publisher-bridge') : __('Blocked', 'wp-draft-publisher-bridge'),
        __('Manage categories', 'wp-draft-publisher-bridge') => current_user_can('manage_categories') ? __('Allowed', 'wp-draft-publisher-bridge') : __('Blocked', 'wp-draft-publisher-bridge'),
        __('Active SEO provider', 'wp-draft-publisher-bridge') => wpdp_bridge_active_seo_provider(),
    );
}

function wpdp_bridge_render_activity_page() {
    if (!current_user_can('edit_posts')) { wp_die(esc_html__('You do not have permission to view this page.', 'wp-draft-publisher-bridge')); }
    $tab = isset($_GET['tab']) ? sanitize_key(wp_unslash($_GET['tab'])) : 'overview';
    if (!in_array($tab, array('overview', 'activity', 'recovery'), true)) { $tab = 'overview'; }
    $base_url = admin_url('tools.php?page=wpdp-activity');
    echo '<div class="wrap wpdp-admin"><h1>' . esc_html__('Draft Publisher', 'wp-draft-publisher-bridge') . '</h1>';
    echo '<p>' . esc_html__('Connect Codex or Claude to safe WordPress draft tools. This plugin never stores AI prompts or WordPress passwords.', 'wp-draft-publisher-bridge') . '</p>';
    echo '<style>.wpdp-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;max-width:1100px}.wpdp-card{background:#fff;border:1px solid #dcdcde;border-radius:6px;padding:18px}.wpdp-card h2{margin-top:0}.wpdp-ready{color:#008a20;font-weight:700}.wpdp-muted{color:#646970}.wpdp-admin code{word-break:break-all}.wpdp-status td:first-child{font-weight:600;width:45%}</style>';
    echo '<nav class="nav-tab-wrapper">';
    foreach (array('overview' => __('Connection', 'wp-draft-publisher-bridge'), 'activity' => __('Activity', 'wp-draft-publisher-bridge'), 'recovery' => __('Recovery', 'wp-draft-publisher-bridge')) as $key => $label) {
        $class = 'nav-tab' . ($tab === $key ? ' nav-tab-active' : '');
        echo '<a class="' . esc_attr($class) . '" href="' . esc_url(add_query_arg('tab', $key, $base_url)) . '">' . esc_html($label) . '</a>';
    }
    echo '</nav>';

    if (isset($_GET['wpdp_message'])) {
        $notice_class = isset($_GET['wpdp_result']) && 'restored' === sanitize_key(wp_unslash($_GET['wpdp_result'])) ? 'notice-success' : 'notice-error';
        echo '<div class="notice ' . esc_attr($notice_class) . ' is-dismissible"><p>' . esc_html(rawurldecode(wp_unslash($_GET['wpdp_message']))) . '</p></div>';
    }

    if ('overview' === $tab) {
        $status_url = add_query_arg('_wpnonce', wp_create_nonce('wp_rest'), rest_url('wp-draft-publisher/v1/status'));
        echo '<div class="wpdp-grid" style="margin-top:20px">';
        echo '<section class="wpdp-card"><h2>' . esc_html__('Server readiness', 'wp-draft-publisher-bridge') . '</h2><p class="wpdp-ready">● ' . esc_html__('Bridge is active', 'wp-draft-publisher-bridge') . '</p>';
        echo '<table class="widefat striped wpdp-status"><tbody>';
        foreach (wpdp_bridge_admin_status_rows() as $label => $value) { echo '<tr><td>' . esc_html($label) . '</td><td>' . esc_html($value) . '</td></tr>'; }
        echo '</tbody></table><p><a class="button" href="' . esc_url($status_url) . '" target="_blank" rel="noopener">' . esc_html__('Open connection test endpoint', 'wp-draft-publisher-bridge') . '</a></p></section>';

        echo '<section class="wpdp-card"><h2>' . esc_html__('Create a dedicated user', 'wp-draft-publisher-bridge') . '</h2><p>' . esc_html__('Use a separate WordPress account so automation access can be revoked without affecting your main login. Editor is the recommended role when category creation is needed.', 'wp-draft-publisher-bridge') . '</p>';
        if (current_user_can('create_users')) { echo '<p><a class="button button-primary" href="' . esc_url(admin_url('user-new.php')) . '">' . esc_html__('Add automation user', 'wp-draft-publisher-bridge') . '</a></p>'; }
        else { echo '<p class="wpdp-muted">' . esc_html__('Ask an administrator to create the dedicated account.', 'wp-draft-publisher-bridge') . '</p>'; }
        echo '<h3>' . esc_html__('Application Password', 'wp-draft-publisher-bridge') . '</h3><p>' . esc_html__('Sign in as the dedicated user, open its profile, create an Application Password, and enter it in the local connection wizard. Do not use the normal account password.', 'wp-draft-publisher-bridge') . '</p><p><a class="button" href="' . esc_url(admin_url('profile.php#application-passwords-section')) . '">' . esc_html__('Open my profile', 'wp-draft-publisher-bridge') . '</a></p></section>';

        echo '<section class="wpdp-card"><h2>' . esc_html__('Connect Codex or Claude', 'wp-draft-publisher-bridge') . '</h2><ol><li>' . esc_html__('Install WP Draft Publisher on the computer that runs the AI client.', 'wp-draft-publisher-bridge') . '</li><li>' . esc_html__('Run the connection wizard and enter this site address, the dedicated username, and its Application Password.', 'wp-draft-publisher-bridge') . '</li><li>' . esc_html__('Restart the AI client and request a WordPress draft.', 'wp-draft-publisher-bridge') . '</li></ol><p><strong>' . esc_html__('Site address:', 'wp-draft-publisher-bridge') . '</strong> <code>' . esc_html(home_url('/')) . '</code></p><p class="wpdp-muted">' . esc_html__('The local wizard verifies authentication, media, categories, tags, SEO, and this bridge before saving encrypted credentials.', 'wp-draft-publisher-bridge') . '</p></section>';

        echo '<section class="wpdp-card"><h2>' . esc_html__('Safety policy', 'wp-draft-publisher-bridge') . '</h2><ul><li>' . esc_html__('Draft creation and draft-only updates', 'wp-draft-publisher-bridge') . '</li><li>' . esc_html__('Published, private, scheduled, pending, and trashed posts are protected', 'wp-draft-publisher-bridge') . '</li><li>' . esc_html__('Snapshots are created before guarded updates', 'wp-draft-publisher-bridge') . '</li><li>' . esc_html__('No publish endpoint is provided', 'wp-draft-publisher-bridge') . '</li><li>' . esc_html__('Credentials and article bodies are excluded from activity records', 'wp-draft-publisher-bridge') . '</li></ul></section>';
        echo '</div>';
    } elseif ('activity' === $tab) {
        $items = wpdp_bridge_activity_items(100);
        echo '<p>' . esc_html__('This log stores operation metadata only. It never stores credentials, prompts, or article body content.', 'wp-draft-publisher-bridge') . '</p>';
        echo '<table class="widefat striped"><thead><tr><th>Date (GMT)</th><th>User</th><th>Action</th><th>Post</th><th>Media IDs</th><th>Status</th><th>Operation</th></tr></thead><tbody>';
        if (!$items) { echo '<tr><td colspan="7">' . esc_html__('No activity recorded yet.', 'wp-draft-publisher-bridge') . '</td></tr>'; }
        foreach ($items as $item) {
            $user = get_userdata($item['user_id']);
            $post_link = get_edit_post_link($item['post_id']);
            echo '<tr><td>' . esc_html($item['created_gmt']) . '</td><td>' . esc_html($user ? $user->display_name : (string) $item['user_id']) . '</td><td>' . esc_html($item['action']) . '</td><td>';
            if ($post_link) { echo '<a href="' . esc_url($post_link) . '">#' . esc_html((string) $item['post_id']) . '</a>'; } else { echo '#' . esc_html((string) $item['post_id']); }
            echo '</td><td>' . esc_html(implode(', ', $item['media_ids'])) . '</td><td>' . esc_html($item['status']) . '</td><td><code>' . esc_html($item['operation_id']) . '</code></td></tr>';
        }
        echo '</tbody></table>';
    } else {
        $snapshots = wpdp_bridge_recent_snapshots(30);
        echo '<p>' . esc_html__('A private recovery point is saved before every guarded draft update. Restore is available only while the target remains a draft.', 'wp-draft-publisher-bridge') . '</p>';
        echo '<table class="widefat striped"><thead><tr><th>Date (GMT)</th><th>Draft</th><th>Kind</th><th>Operation</th><th>Action</th></tr></thead><tbody>';
        if (!$snapshots) { echo '<tr><td colspan="5">' . esc_html__('No recovery snapshots are available.', 'wp-draft-publisher-bridge') . '</td></tr>'; }
        foreach ($snapshots as $snapshot) {
            $post_link = get_edit_post_link($snapshot['post_id']);
            echo '<tr><td>' . esc_html($snapshot['created_gmt']) . '</td><td><a href="' . esc_url($post_link) . '">' . esc_html($snapshot['title'] ? $snapshot['title'] : '#' . $snapshot['post_id']) . '</a></td><td>' . esc_html($snapshot['kind']) . '</td><td><code>' . esc_html($snapshot['operation_id']) . '</code></td><td>';
            if ($snapshot['can_restore']) {
                echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '" onsubmit="return confirm(\'' . esc_js(__('Restore this draft to the selected recovery point?', 'wp-draft-publisher-bridge')) . '\');"><input type="hidden" name="action" value="wpdp_restore_snapshot"><input type="hidden" name="snapshot_id" value="' . esc_attr((string) $snapshot['snapshot_id']) . '">';
                wp_nonce_field('wpdp_restore_snapshot_' . $snapshot['snapshot_id']);
                submit_button(__('Restore', 'wp-draft-publisher-bridge'), 'secondary small', 'submit', false);
                echo '</form>';
            } else { echo '<span class="wpdp-muted">' . esc_html__('Protected: no longer a draft', 'wp-draft-publisher-bridge') . '</span>'; }
            echo '</td></tr>';
        }
        echo '</tbody></table>';
    }
    echo '</div>';
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
