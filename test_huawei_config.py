#!/usr/bin/env python
"""Test Huawei configuration profile mapping"""
import config

print('=== Perfiles por Modelo ===')
print('EG8021V5:', config.get_huawei_profiles_for_ont_model('EG8021V5'))
print('EG8141A5:', config.get_huawei_profiles_for_ont_model('EG8141A5'))
print('HG8245H:', config.get_huawei_profiles_for_ont_model('HG8245H'))
print('DESCONOCIDO:', config.get_huawei_profiles_for_ont_model('UNKNOWN_MODEL'))

print()
print('=== Parametros Basicos ===')
params = config.get_huawei_injection_params()
for k, v in sorted(params.items()):
    print(f'{k}: {v}')
