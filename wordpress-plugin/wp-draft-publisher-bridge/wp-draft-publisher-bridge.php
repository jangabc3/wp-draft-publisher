<?php
/**
 * Plugin Name: Draft Publisher REST Bridge
 * Description: Exposes permission-checked SEO metadata and an atomic draft-only REST update guard for WP Draft Publisher.
 * Version: 1.1.0
 * Requires at least: 5.6
 * Requires PHP: 7.4
 * License: GPL-2.0-or-later
 * License URI: https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain: wp-draft-publisher-bridge
 */

if (!defined('ABSPATH')) {
    exit;
}

define('WPDP_BRIDGE_VERSION', '1.1.0');

/**
 * Limit registered fields to the Rank Math values used by the publisher.
 */
function wpdp_bridge_register_rank_math_meta() {
    $fields = array(
        'rank_math_title',
        'rank_math_description',
        'rank_math_focus_keyword',
    );

    foreach ($fields as $field) {
        register_post_meta(
            'post',
            $field,
            array(
                'type'              => 'string',
                'single'            => true,
                'show_in_rest'      => true,
                'sanitize_callback' => 'sanitize_text_field',
                'auth_callback'     => function ($allowed, $meta_key, $post_id) {
                    return current_user_can('edit_post', $post_id);
                },
            )
        );
    }
}
add_action('init', 'wpdp_bridge_register_rank_math_meta', 20);

/**
 * Reject a tool-tagged REST update if the post is no longer a draft.
 */
function wpdp_bridge_guard_draft_update($prepared_post, $request) {
    if ('1' !== $request->get_header('x-wpdp-draft-only')) {
        return $prepared_post;
    }

    $post_id = absint($request->get_param('id'));
    if (!$post_id) {
        return new WP_Error(
            'wpdp_missing_post_id',
            __('A draft-only update requires a valid post ID.', 'wp-draft-publisher-bridge'),
            array('status' => 400)
        );
    }

    if ('draft' !== get_post_status($post_id)) {
        return new WP_Error(
            'wpdp_post_not_draft',
            __('The post is no longer a draft.', 'wp-draft-publisher-bridge'),
            array('status' => 409)
        );
    }

    $expected_modified_gmt = $request->get_header('x-wpdp-expected-modified-gmt');
    if ($expected_modified_gmt) {
        $current_modified_gmt = get_post_field('post_modified_gmt', $post_id, 'raw');
        if (!$current_modified_gmt || !hash_equals($current_modified_gmt, $expected_modified_gmt)) {
            return new WP_Error(
                'wpdp_post_changed_since_read',
                __('The draft changed after the agent read it. Reload and review the latest version before saving.', 'wp-draft-publisher-bridge'),
                array(
                    'status'               => 409,
                    'current_modified_gmt' => $current_modified_gmt,
                )
            );
        }
    }

    return $prepared_post;
}
add_filter('rest_pre_insert_post', 'wpdp_bridge_guard_draft_update', 10, 2);

function wpdp_bridge_status_permission() {
    return current_user_can('edit_posts');
}

function wpdp_bridge_status() {
    return rest_ensure_response(
        array(
            'version'            => WPDP_BRIDGE_VERSION,
            'atomic_draft_guard' => true,
            'optimistic_locking' => true,
            'rank_math_meta'     => array(
                'rank_math_title',
                'rank_math_description',
                'rank_math_focus_keyword',
            ),
        )
    );
}

function wpdp_bridge_register_routes() {
    register_rest_route(
        'wp-draft-publisher/v1',
        '/status',
        array(
            'methods'             => WP_REST_Server::READABLE,
            'callback'            => 'wpdp_bridge_status',
            'permission_callback' => 'wpdp_bridge_status_permission',
        )
    );
}
add_action('rest_api_init', 'wpdp_bridge_register_routes');
