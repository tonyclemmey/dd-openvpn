import socket
from checks import AgentCheck

class OpenVPNCheck(AgentCheck):
  def check(self, instance):

    # Make sure expected parameters are present
    if 'domain' not in instance:
      self.log.info("Skipping instance, no domain found")
      return

    if 'port' not in instance:
      self.log.info("Skipping instance, no port found")

    # Load values from instance config
    domain = instance['domain']
    port = instance['port']
    timeout = self.init_config.get('default_timeout', 5)
    tags = instance.get('tags', [])

    # Prepare a socket
    try:
      ipaddress = socket.gethostbyname(domain)
    except socket.error as e:
      self.log.error("Unable to get IP for %s: %s" % (domain, e))
      return

    # Connect to OpenVPN management port
    try:
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      s.settimeout(timeout)
      s.connect((ipaddress, port))

      data = s.makefile('rb')
      line = data.readline()
      if not line.startswith(b'>INFO:OpenVPN'):
        self.log.error("Unexpected OpenVPN output: %s" %s (line.rstrip()))
        s.close()
        return

      # Request load statistics (in order: number of connected users, bytes in, bytes out)
      s.send(b'load-stats\r\n')

      # Strip trailing whitespaces and "SUCCESS: " prefix
      line = data.readline().rstrip().lstrip(b'SUCCESS: ')

      # Done with socket for now
      s.close()

      # Metrics separated by commas; metric name and value separated by =
      ovpn_metrics = line.split(b',')
      for item in ovpn_metrics:
        metric = item.split(b'=')
        self.gauge('openvpn.' + metric[0].decode(), metric[1].decode(), tags=tags)

    except socket.timeout:
      self.log.error("Timed out trying to connect to OpenVPN: %s" % (e))
      self.gauge('openvpn.timeout', -1, tags=tags)
      return

    except socket.error as e:
      self.log.error("Exception while trying to connect to OpenVPN: %s" % (e))
      self.gauge('openvpn.error', -2, tags=tags)
      return

if __name__ == '__main__':
  check, instances = OpenVPNCheck.from_yaml('/etc/datadog-agent/conf.d/openvpn.yaml')
  for instance in instances:
    check.check(instance)
