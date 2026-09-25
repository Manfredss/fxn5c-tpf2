"""User-requested markings, not certification of real-world allocations/dates."""
ROSTER = [
    dict(stem='fxn5c', number='0051', depot='上局沪段', jinwen=False),
    dict(stem='fxn5c_0096', number='0096', depot='上局宁东段', jinwen=False),
    dict(stem='fxn5c_0102', number='0102', depot='上局宁东段', jinwen=False),
    dict(stem='fxn5c_0057', number='0057', depot='上局杭段', jinwen=False),
    dict(stem='fxn5c_0081', number='0081', depot='上局杭段', jinwen=False),
    dict(stem='fxn5c_0066', number='0066', depot='上局沪段', jinwen=False),
    dict(stem='fxn5c_0035', number='0035', depot='上局徐段', jinwen=False),
    dict(stem='fxn5c_0115', number='0115', depot='上局徐段', jinwen=False),
    dict(stem='fxn5c_jinwen', number='7006', depot='金温 温段', jinwen=True),
    dict(stem='fxn5c_jinwen_7005', number='7005', depot='金温 温段', jinwen=True),
]


def description_key(row):
    return 'VEHICLE_FXN5C_'+row['number']


def group_stem(row):
    return 'fxn5c_menu_jinwen' if row['jinwen'] else 'fxn5c_menu_cr'
