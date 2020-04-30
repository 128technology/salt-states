import subprocess

def main():
  routes = subprocess.check_output(['ip','r']).decode().split('\n')
  gateways = {}
  for route in routes:
    if 'default' in route:
      route_split = route.split(' ')
      gateways[route_split[4]] = route_split[2]
  grains = {}
  grains['gateways'] = gateways
  return grains
