{
    'name': "Destination Management",
    'version': '1.0',
    'depends': ['base_automation','sale'],
    'author': "Sumworks",
    'category': 'Sales',
    'description': """
    Management of Destinations
    """,
    'application': True,
    # data files always loaded at installation
    'data':[
        'security/ir_module_category.xml',
        'security/res_groups.xml',
        'views/ir_ui_view.xml',
        'views/ir_actions_act_window.xml',
        'views/ir_actions_act_window_view.xml',
        'views/ir_ui_menu.xml',
        'views/ir_default.xml',
        'report/dest_rental_report_templates.xml',
        'report/dest_rental_report.xml',
        'data/ir_sequence_data.xml',
        'data/base_automation.xml',
        'data/online_guest_form.xml',
        'data/email_temp.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',

        
        

    ]
}