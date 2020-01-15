# Ensure atop is not masked and enabled

atop:
  service.running:
    - enable: True
    - unmask: True
