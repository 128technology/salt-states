# Ensure atop is not masked and enabled

atop:
  pkg:
    - installed
  service.running:
    - enable: True
    - unmask: True
