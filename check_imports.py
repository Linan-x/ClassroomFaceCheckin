import importlib, traceback
modules = ['torch','torchvision','mxnet','cv2','numpy','PIL','matplotlib','scipy']
results = {}
for m in modules:
    try:
        mod = importlib.import_module(m)
        ver = getattr(mod, '__version__', 'unknown')
        results[m] = f'OK, version={ver}'
    except Exception as e:
        results[m] = 'ERROR: ' + ''.join(traceback.format_exception_only(type(e), e)).strip()
for k,v in results.items():
    print(f'{k}: {v}')
