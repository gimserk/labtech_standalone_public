from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from app import views as app_views
from django.views.static import serve

urlpatterns = [
    # Django Admin
    path('admin/help-desk/tickets/', app_views.admin_ticket_list_view, name='admin_ticket_list'),
    path('admin/', admin.site.urls),

    # Allauth URLs (for social login processing, password reset, etc.)
    path('accounts/', include('allauth.urls')),

    # Main public website URLs
    path('', app_views.home_view, name='home'),
    path('features/', app_views.features_view, name='features'),
    path('courses/', app_views.courseware_view, name='courseware'),
    path('course/<int:course_id>/', app_views.public_course_detail_view, name='course_detail_public'),
    path('community/', app_views.community_view, name='community'),
    path('subscription/', app_views.subscription_view, name='subscription'),
    path('support/', app_views.support_view, name='support'),
    path('signup/', app_views.signup_view, name='signup'),
    path('login/', app_views.login_view, name='login'),

    # LabTech Application URLs (Admin/Management Section)
    path('labtech/dashboard/', app_views.labtech_dashboard_view, name='labtech_home'),

    #ckeditor
    path('ckeditor/', include('ckeditor_uploader.urls')),

    # Institution Management URLs
    path('labtech/institutions/', app_views.manage_institutions_list_view, name='labtech_manage_institutions_list'),
    path('labtech/institutions/add/', app_views.add_institution_view, name='labtech_add_institution'),
    path('labtech/institutions/<int:institution_id>/', app_views.manage_single_institution_view, name='labtech_manage_single_institution'),
    path('labtech/institutions/<int:institution_id>/edit/', app_views.edit_institution_view, name='labtech_edit_institution'),
    path('institutions/<int:institution_id>/users/<int:profile_id>/edit-role/', app_views.edit_institution_user_role_view, name='labtech_edit_institution_user_role'),
    path('institutions/<int:institution_id>/users/<int:profile_id>/remove/', app_views.remove_user_from_institution_view, name='labtech_remove_institution_user'),
    path('institution/<int:institution_id>/courses/', app_views.view_institution_courses_list, name='view_institution_courses_list'),
    path('institutions/<int:institution_id>/assign-plan/', app_views.assign_plan_to_institution_view, name='labtech_assign_plan_to_institution'),
    
    # User Management within an Institution
    path('labtech/institutions/<int:institution_id>/users/', app_views.manage_institution_users_view, name='manage_institution_users'),
    path('labtech/institutions/<int:institution_id>/users/add/', app_views.add_user_to_institution_view, name='add_user_to_institution'),
    # (You'll add URLs for editing/removing institution users here later)

    # Course Management (Admin / Institution Admin)
    path('labtech/courses/', app_views.manage_courses_list_view, name='labtech_manage_courses_list'), # For Site Admins (all courses)
    path('labtech/courses/add/', app_views.add_course_view, name='labtech_add_course'), # For Site Admins (public or assign to any inst.)
    path('labtech/institution/<int:institution_id>/courses/', app_views.manage_courses_list_view, name='labtech_manage_courses_list_for_institution'), # For Inst. Admins
    path('labtech/institution/<int:institution_id>/courses/add/', app_views.add_course_view, name='labtech_add_course_for_institution'), # For Inst. Admins
    path('labtech/courses/<int:course_id>/edit/', app_views.edit_course_view, name='labtech_edit_course'),
    path('labtech/courses/<int:course_id>/delete/', app_views.delete_course_view, name='labtech_delete_course'),
    # (You'll add URLs for managing course content like pages, labs, quizzes here later)

    # Subscription Plan Management (Admin)
    path('labtech/subscriptions/plans/', app_views.manage_subscription_plans_list_view, name='labtech_manage_subscription_plans_list'),
    path('labtech/subscriptions/plans/add/', app_views.add_subscription_plan_view, name='labtech_add_subscription_plan'),
    path('labtech/subscriptions/plans/<int:plan_id>/edit/', app_views.edit_subscription_plan_view, name='labtech_edit_subscription_plan'),

    # User Subscription Management (Admin)
    path('labtech/subscriptions/users/', app_views.manage_user_subscriptions_list_view, name='labtech_manage_user_subscriptions_list'),
    path('labtech/subscriptions/users/assign/', app_views.assign_user_subscription_view, name='labtech_assign_user_subscription'), # General assign page
    path('labtech/subscriptions/users/assign/<int:user_id>/', app_views.assign_user_subscription_view, name='labtech_assign_user_subscription_to_user'), # Assign to specific user
    path('labtech/subscriptions/users/<int:subscription_id>/edit/', app_views.edit_user_subscription_view, name='labtech_edit_user_subscription'),

    # New URL for managing content of a specific course
    path('courses/<int:course_id>/content/', app_views.manage_course_content_view, name='labtech_manage_course_content'),

    # TextPage Content CRUD URLs
    path('courses/<int:course_id>/textpages/add/', app_views.add_text_page_view, name='labtech_add_text_page'),
    path('courses/<int:course_id>/textpages/<int:page_id>/edit/', app_views.edit_text_page_view, name='labtech_edit_text_page'),
    path('courses/<int:course_id>/textpages/<int:page_id>/delete/', app_views.delete_text_page_view, name='labtech_delete_text_page'),

    # Video Content CRUD URLs
    path('courses/<int:course_id>/videos/add/', app_views.add_video_view, name='labtech_add_video'),
    path('courses/<int:course_id>/videos/<int:video_id>/edit/', app_views.edit_video_view, name='labtech_edit_video'),
    path('courses/<int:course_id>/videos/<int:video_id>/delete/', app_views.delete_video_view, name='labtech_delete_video'),

    # Quiz Content (Quiz Details) CRUD URLs
    path('courses/<int:course_id>/quizzes/add/', app_views.add_quiz_view, name='labtech_add_quiz'),
    path('courses/<int:course_id>/quizzes/<int:quiz_id>/edit/', app_views.edit_quiz_view, name='labtech_edit_quiz'),
    path('courses/<int:course_id>/quizzes/<int:quiz_id>/delete/', app_views.delete_quiz_view, name='labtech_delete_quiz'),

    # Quiz Question Management URLs
    path('courses/<int:course_id>/quizzes/<int:quiz_id>/questions/', app_views.manage_quiz_questions_view, name='labtech_manage_quiz_questions'),
    path('courses/<int:course_id>/quizzes/<int:quiz_id>/questions/add/', app_views.add_question_to_quiz_view, name='labtech_add_question_to_quiz'),
    path('courses/<int:course_id>/quizzes/<int:quiz_id>/questions/<int:question_id>/edit/', app_views.edit_question_in_quiz_view, name='labtech_edit_question_in_quiz'),
    path('courses/<int:course_id>/quizzes/<int:quiz_id>/questions/<int:question_id>/delete/', app_views.delete_question_from_quiz_view, name='labtech_delete_question_from_quiz'),

    # Proxmox Server Management URLs
    path('proxmox/servers/', app_views.manage_proxmox_servers_list_view, name='labtech_manage_proxmox_servers_list'),
    path('proxmox/servers/add/', app_views.add_proxmox_server_view, name='labtech_add_proxmox_server'),
    path('proxmox/servers/<int:server_id>/edit/', app_views.edit_proxmox_server_view, name='labtech_edit_proxmox_server'),
    path('proxmox/servers/<int:server_id>/delete/', app_views.delete_proxmox_server_view, name='labtech_delete_proxmox_server'),
    path('proxmox/servers/<int:server_id>/sync-templates/', app_views.sync_proxmox_templates_view, name='labtech_sync_proxmox_templates'),

    # Lab Content (Lab Details) CRUD URLs
    path('courses/<int:course_id>/labs/add/', app_views.add_lab_view, name='labtech_add_lab'),
    path('courses/<int:course_id>/labs/<int:lab_id>/edit/', app_views.edit_lab_view, name='labtech_edit_lab'),
    path('courses/<int:course_id>/labs/<int:lab_id>/delete/', app_views.delete_lab_view, name='labtech_delete_lab'),
    
    # Lab Step Management URLs
    path('courses/<int:course_id>/labs/<int:lab_id>/steps/', app_views.manage_lab_steps_view, name='labtech_manage_lab_steps'),
    path('courses/<int:course_id>/labs/<int:lab_id>/steps/add/', app_views.add_step_to_lab_view, name='labtech_add_step_to_lab'),
    path('courses/<int:course_id>/labs/<int:lab_id>/steps/<int:step_id>/edit/', app_views.edit_step_in_lab_view, name='labtech_edit_step_in_lab'),
    path('courses/<int:course_id>/labs/<int:lab_id>/steps/<int:step_id>/delete/', app_views.delete_step_from_lab_view, name='labtech_delete_step_from_lab'),

    # Article (Community/News) Management URLs
    path('labtech/community/articles/', app_views.manage_articles_list_view, name='labtech_manage_articles_list'),
    path('labtech/community/articles/add/', app_views.add_article_view, name='labtech_add_article'),
    path('labtech/community/articles/<int:article_id>/edit/', app_views.edit_article_view, name='labtech_edit_article'),
    path('labtech/community/articles/<int:article_id>/delete/', app_views.delete_article_view, name='labtech_delete_article'),
    path('community/article/<slug:slug>/', app_views.public_article_detail_view, name='article_detail'),

    # Course Catalog
    path('coursecatalog/', app_views.course_catalog_view, name='course_catalog'),
    path('courses/<int:course_id>/enroll/', app_views.enroll_in_course_view, name='enroll_in_course'),
    path('courses/<int:course_id>/', app_views.course_detail_view, name='course_detail'),
    path('courses/<int:course_id>/content/<str:content_type_name>/<int:object_id>/complete/', app_views.mark_content_complete_view, name='mark_content_complete'),
    path('courses/<int:course_id>/manage/', app_views.manage_course_content_view, name='manage_course_content'),
    path('courses/<int:course_id>/chapters/add/', app_views.add_chapter_view, name='add_chapter'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/edit/', app_views.edit_chapter_view, name='edit_chapter'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/delete/', app_views.delete_chapter_view, name='delete_chapter'),
    path('courses/<int:course_id>/unenroll/', app_views.unenroll_from_course_view, name='unenroll_from_course'),

    # Student Quiz
    path('courses/<int:course_id>/quizzes/<int:quiz_id>/take/', app_views.take_quiz_view, name='take_quiz'),
     path('courses/<int:course_id>/quizzes/attempt/<int:attempt_id>/results/', app_views.quiz_result_view, name='quiz_result'),

    # URL for the student's lab dashboard page
    path('courses/<int:course_id>/labs/<int:lab_id>/', app_views.view_lab_view, name='view_lab'),
    
    # URL to trigger the creation of a lab instance
    path('courses/<int:course_id>/labs/<int:lab_id>/create/', app_views.create_lab_instance_view, name='create_lab_instance'),
    
    # URL to handle power actions (start, stop, etc.) and finishing (deleting) the lab
    path('courses/<int:course_id>/lab-instances/<int:instance_id>/action/<str:action>/', app_views.lab_instance_action_view, name='lab_instance_action'),

    # Guacamole Server Management URLs (NEW SECTION)
    path('labtech/guacamole/servers/', app_views.manage_guacamole_servers_list_view, name='labtech_manage_guacamole_servers_list'),
    path('labtech/guacamole/servers/add/', app_views.add_guacamole_server_view, name='labtech_add_guacamole_server'),
    path('labtech/guacamole/servers/<int:server_id>/edit/', app_views.edit_guacamole_server_view, name='labtech_edit_guacamole_server'),
    path('labtech/guacamole/servers/<int:server_id>/delete/', app_views.delete_guacamole_server_view, name='labtech_delete_guacamole_server'),

    # Docker Server Management URLs
    path('servers/', app_views.manage_docker_servers_list_view, name='labtech_manage_docker_servers_list'),
    path('servers/add/', app_views.add_docker_server_view, name='labtech_add_docker_server'),
    path('servers/<int:server_id>/edit/', app_views.edit_docker_server_view, name='labtech_edit_docker_server'),
    path('servers/<int:server_id>/delete/', app_views.delete_docker_server_view, name='labtech_delete_docker_server'),

    # Docker Image Management URLs
    path('images/', app_views.manage_docker_images_list_view, name='labtech_manage_docker_images_list'),
    path('images/add/', app_views.add_docker_image_view, name='labtech_add_docker_image'),
    path('images/<int:image_id>/edit/', app_views.edit_docker_image_view, name='labtech_edit_docker_image'),
    path('images/<int:image_id>/delete/', app_views.delete_docker_image_view, name='labtech_delete_docker_image'),

    # ... your existing lab and other urls ...
    path('lab-steps/questions/<int:question_id>/check/', app_views.check_step_answer_view, name='check_step_answer'),
    path('courses/<int:course_id>/labs/<int:lab_id>/steps/<int:step_id>/questions/add/', app_views.add_step_question_view, name='add_step_question'),
    path('courses/<int:course_id>/labs/<int:lab_id>/steps/<int:step_id>/questions/<int:question_id>/edit/', app_views.edit_step_question_view, name='edit_step_question'),
    path('courses/<int:course_id>/labs/<int:lab_id>/steps/<int:step_id>/questions/<int:question_id>/delete/', app_views.delete_step_question_view, name='delete_step_question'),

    # URL for a user to edit their own profile
    path('profile/edit/', app_views.profile_edit_view, name='profile_edit'),
    
    # URL to view any user's profile using their unique usertag
    path('profile/<int:user_id>/', app_views.profile_detail_view, name='profile_detail'),

    path('mysubscription/', app_views.manage_my_subscription_view, name='manage_my_subscription'),
    path('subscription/change/<int:plan_id>/', app_views.change_subscription_plan_view, name='change_subscription_plan'),
    path('my-courses/', app_views.my_courses_view, name='my_courses'),

    # Gradebooks
    path('courses/<int:course_id>/instructor-gradebook/', app_views.instructor_gradebook_view, name='instructor_gradebook'),
    path('courses/<int:course_id>/my-grades/', app_views.my_course_grades_view, name='my_course_grades'),

    # Helpdesk
    path('help/', app_views.help_desk_portal_view, name='help_desk_portal'),
    path('help/tickets/', app_views.my_tickets_view, name='my_tickets'),
    path('help/tickets/new/', app_views.create_ticket_view, name='create_ticket'),
    path('help/tickets/<int:ticket_id>/', app_views.ticket_detail_view, name='ticket_detail'),

    # Payments
    path('subscription/success/', app_views.payment_success_view, name='payment_success'),
    path('subscribe/create/<int:plan_id>/', app_views.create_payment_view, name='create_payment'),
    path('subscribe/process/<int:payment_id>/', app_views.process_payment_view, name='process_payment'),
    path('payments/', include('payments.urls')),

    # Instructor Views
    path('labtech/my-teaching-courses/', app_views.instructor_my_courses_view, name='instructor_my_courses'),
    path('labtech/instructor/courses/add/', app_views.instructor_add_course_view, name='instructor_add_course'),
    path('courses/<int:course_id>/import/', app_views.import_content_view, name='import_content'),
    path('api/course-content/<int:course_id>/', app_views.get_course_content_json_view, name='api_get_course_content'),
    path('labtech/courses/<int:course_id>/students/', app_views.instructor_student_list_view, name='instructor_student_list'),
    path('labtech/courses/<int:course_id>/enroll-student/', app_views.instructor_enroll_student_view, name='instructor_enroll_student'),
    path('labtech/courses/<int:course_id>/announcements/', app_views.manage_announcements_view, name='manage_announcements'),
    path('labtech/courses/<int:course_id>/announcements/add/', app_views.add_announcement_view, name='add_announcement'),
    path('labtech/courses/<int:course_id>/announcements/<int:announcement_id>/edit/', app_views.edit_announcement_view, name='edit_announcement'),
    path('labtech/courses/<int:course_id>/announcements/<int:announcement_id>/delete/', app_views.delete_announcement_view, name='delete_announcement'),
    path('labtech/courses/<int:course_id>/resources/', app_views.manage_course_resources_view, name='manage_course_resources'),
    path('labtech/resources/<int:resource_id>/delete/', app_views.delete_course_resource_view, name='delete_course_resource'),
    path('labtech/resources/<int:resource_id>/edit/', app_views.edit_course_resource_view, name='edit_course_resource'),
    path('enrollments/<int:enrollment_id>/remove/', app_views.remove_student_from_course_view, name='remove_student_from_course'),
    path('labtech/subscriptions/plans/update-order/', app_views.update_plan_order_view, name='labtech_update_plan_order'),
    path('labtech/courses/<int:course_id>/notifications/compose/', app_views.compose_notification_view, name='compose_notification'),
    path('labtech/courses/<int:course_id>/notifications/log/', app_views.notification_log_view, name='notification_log'),

    path('labtech/courses/<int:course_id>/update-content-order/', app_views.update_content_order_view, name='update_content_order'),

    #STRIPE URLS
    path('create-checkout-session/', app_views.create_checkout_session_view, name='create_checkout_session'),
    path('subscribe/success/', app_views.payment_success_view, name='payment_success'),
    path('subscribe/cancelled/', app_views.payment_cancelled_view, name='payment_cancelled'),
    path('stripe/webhook/', app_views.stripe_webhook_view, name='stripe_webhook'),
    path('subscribe/customer-portal/', app_views.create_customer_portal_session_view, name='customer_portal'),

    #FAQs
    path('labtech/faqs/category/<int:category_id>/', app_views.manage_faqs_in_category_view, name='manage_faqs_in_category'),
    path('labtech/faqs/category/<int:category_id>/add/', app_views.add_faq_view, name='add_faq'),
    path('labtech/faqs/<int:faq_id>/edit/', app_views.edit_faq_view, name='edit_faq'),
    path('labtech/faqs/<int:faq_id>/delete/', app_views.delete_faq_view, name='delete_faq'),
    path('labtech/faqs/categories/', app_views.manage_faq_categories_view, name='manage_faq_categories'),
    path('labtech/faqs/categories/add/', app_views.add_faq_category_view, name='add_faq_category'),
    path('labtech/faqs/categories/<int:category_id>/edit/', app_views.edit_faq_category_view, name='edit_faq_category'),
    path('labtech/faqs/categories/<int:category_id>/delete/', app_views.delete_faq_category_view, name='delete_faq_category'),
    path('labtech/faqs/add/', app_views.global_add_faq_view, name='global_add_faq'),

    path('courses/<int:course_id>/bulk-update-dates/', app_views.bulk_update_content_dates_view, name='bulk_update_content_dates'),

    path('labtech/template-library/', app_views.template_library_view, name='template_library'),
    path('labtech/template-library/<int:template_id>/edit/', app_views.edit_template_details_view, name='edit_template_details'),

    # =============================================================================
    # CYBERCITY URLS
    # =============================================================================
    path('labtech/cybercity/', app_views.cybercity_dashboard_view, name='cybercity_dashboard'),
    path('labtech/cybercity/add/', app_views.cybercity_add_view, name='cybercity_add'),
    path('labtech/cybercity/<int:city_id>/', app_views.cybercity_detail_view, name='cybercity_detail'),
    path('labtech/cybercity/<int:city_id>/edit/', app_views.cybercity_edit_view, name='cybercity_edit'),
    path('labtech/cybercity/<int:city_id>/delete/', app_views.cybercity_delete_view, name='cybercity_delete'),
    path('labtech/cybercity/<int:city_id>/check-broker-status/', app_views.check_broker_status_view, name='cybercity_check_broker_status'),
    
    # CyberCity Building URLs
    path('labtech/cybercity/<int:city_id>/buildings/add/', app_views.cybercity_building_add_view, name='cybercity_building_add'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/', app_views.cybercity_building_detail_view, name='cybercity_building_detail'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/edit/', app_views.cybercity_building_edit_view, name='cybercity_building_edit'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/delete/', app_views.cybercity_building_delete_view, name='cybercity_building_delete'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/get-statuses/', app_views.cybercity_get_pin_statuses_view, name='cybercity_get_pin_statuses'),
    
    # CyberCity Machine URLs
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/machines/add/', app_views.cybercity_machine_add_view, name='cybercity_machine_add'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/machines/<int:machine_id>/edit/', app_views.cybercity_machine_edit_view, name='cybercity_machine_edit'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/machines/<int:machine_id>/delete/', app_views.cybercity_machine_delete_view, name='cybercity_machine_delete'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/machines/<int:machine_id>/<str:action>/', app_views.cybercity_machine_action_view, name='cybercity_machine_action'),

    # CyberCity ESP32 URLs
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/esp32/add/', app_views.cybercity_esp32_add_view, name='cybercity_esp32_add'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/esp32/<int:esp32_id>/', app_views.cybercity_esp32_detail_view, name='cybercity_esp32_detail'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/esp32/<int:esp32_id>/delete/', app_views.cybercity_esp32_delete_view, name='cybercity_esp32_delete'),
    
    # CyberCity Attack Monitor URLs
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/monitors/add/', app_views.cybercity_attack_monitor_add_view, name='cybercity_attack_monitor_add'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/monitors/<int:monitor_id>/edit/', app_views.cybercity_attack_monitor_edit_view, name='cybercity_attack_monitor_edit'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/monitors/<int:monitor_id>/delete/', app_views.cybercity_attack_monitor_delete_view, name='cybercity_attack_monitor_delete'),
    path('labtech/cybercity/<int:city_id>/buildings/<int:building_id>/monitors/<int:monitor_id>/trigger/', app_views.cybercity_trigger_attack_view, name='cybercity_trigger_attack'),
]

handler404 = app_views.custom_page_not_found_view
handler500 = app_views.custom_server_error_view

urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]