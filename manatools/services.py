# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:
'''
Python manatools.services contains systemd services backend

This module aims to share all the API to manage system services,
to be used from GUI applications or console.

License: LGPLv2+

Author:  Angelo Naselli <anaselli@linux.it>

@package manatools.services
'''

import os.path
from subprocess import run, CalledProcessError, TimeoutExpired
from pystemd.dbuslib import DBus
from pystemd.systemd1 import Manager, Unit


class Services():
    '''
    Services provides an easy access to systemd services
    '''
    def __init__(self):
        '''
        Services constructor
        '''
        self._bus = None
        self.__manager = None
        # self._systemd = self._bus.get_object('org.freedesktop.systemd1',
        #                                     '/org/freedesktop/systemd1')
        self.include_static_services = False
        self._reload = True
        self._services = {}
        self._xinetd_services = {}

    @property
    def manager(self):
        '''
        Returns the Service Manager Interface
        '''
        if not self.__manager:
            self.__manager = Manager(bus=self.bus)
        return self.__manager
    
    @property
    def bus(self):
        '''
        Returns the bus interface
        '''
        if not self._bus:
            self._bus = DBus(interactive=True)
        return self._bus

    @property    
    def service_info(self):
        '''
        A dictionary collecting all the service information.
        if include_static_services (default is false) is set also static
        services are included.
        '''
        if not self._reload:
            return self._services

        units = []# self.manager.ListUnit()
        self._services = {}
        self._reload = False
        
        for u in units:
            unitName = u[0] #### name
            pos = unitName.find(".service")
            if pos != -1 :
                try:
                    if unitName.find("@") == -1 :
                        st = self.manager.GetUnitFileState(unitName)
                        name = unitName[0:pos]
                        if st and (self.include_static_services or st != 'static'):
                            self._services[name] = {
                                'name':        u[0],
                                'description': u[1],
                                'load_state':  u[2],
                                'active_state':u[3],
                                'sub_state':   u[4],
                                'unit_path':   u[6],
                                'enabled'  :   st == 'enabled',
                            }
                        # TODO if not st check unit files see Services.pm:167
                except: 
                    pass   
        
        unit_files = self.manager.ListUnitFiles()
        for u in unit_files:
            unitName = u[0]
            st = u[1]
            pos = unitName.find(".service")
            if pos != -1 :
                name = os.path.basename(unitName)
                name = name[0:name.find(".service")]
                if (not name in self._services.keys()) and (name.find('@') == -1) \
                    and (os.path.isfile(unitName) or os.path.isfile("/etc/rc.d/init.d/"+name)) \
                        and not os.path.islink(unitName) and (st == "disabled" or st == "enabled"):
                    # Get service state :
                    if run(["/usr/sbin/service", name, "status"]).returncode == 0:
                        active = "active"
                    else:
                        active = "inactive"
                    self._services[name] = {
                                'name':        name+".service",
                                #'description': ####TODO get property,
                                'description': "---",
                                'active_state': active,
                                'enabled'  :   st == 'enabled',
                            }
 
        return self._services
    
    def is_service_running(self, service):
        '''
        @param service: Service to check
        This function returns if the giver service is running
        '''
        try:
            if self._services[service]['active_state'] == "active":
                return True
            else:
                return False
        except KeyError:
            return False
        
    def xinetd_services(self):
        '''
        This function return all xinetd services in this system.
        NOTE that xinetd *must* be enable at boot to get this info.
        '''
        # Avoid warning if xinetd is not installed and either enabled
        try:
            ser_info = self._services['xinetd']
            if ser_info['enabled'] == 'enabled':
                env = {'LANGUAGE': 'C'}
                try:
                    chkconf = run(["/usr/sbin/chkconfig", "--list", "--type", 
                                   "xinetd"], capture_output=True, text=True, 
                                  env=env, timeout=120, check=True)
                    for service in chkconf.stdout.strip().split('\n'):
                        servT = serv.split()
                        try:
                            self._xinetd_services[servT[0].strip(":")] = \
                                servT[1] == 'on'
                        except IndexError:
                            continue
                except (CalledProcessError, TimeoutExpired):
                    # TODO return an exception to the exterior
                    print("chkconfig error when trying to list xinetd services", 
                          stderr)
        except KeyError:
            pass
        
    def _systemd_services(self, reload):
        '''
        Reload service list
        '''
        if reload:
            self.service_info()
        
    def set_service(self, service, enable):
        '''
        @param service: service name
        @param enable: enable/disable service
        This function enable/disable at boot the given service
        '''
        legacy = os.path.isfile("/etc/rc.d/init.d/{}".format(service))
        if service in self._xinetd_services.keys():
            env = {'PATH': "/usr/bin:/usr/sbin"}
            try:
                run(["/usr/bin/pkexec", "/usr/sbin/chkconfig", 
                     "--add" if enable else "--del", service], env=env, 
                    timeout=120, check=True)
            except (CalledProcessError, TimeoutExpired):
                # TODO return an exception to the exterior
                print("chkconfig error when trying to add/delete service",
                      stderr)
        # NOTE check if systemd exists is not implemented because if not 
        # I think pystemd will fail.
        # However it could be implemented latter
        elif not legacy:
            service = service+".service"
            if enable:
                self.bus.EnableUnitFiles(service, False, True)
            else:
                self.bus.DisableUnitFiles(service, False)
        else:
            script = "/etc/rc.d/init.d/" + service
            env = {'PATH': "/usr/bin:/usr/sbin"}
            try:
                run(["/usr/bin/pkexec", "/usr/sbin/chkconfig", 
                     "--add" if enable else "--del", service], env=env,
                    timeout=120, check=True)
            except (CalledProcessError, TimeoutExpired):
                # TODO return an exception to the exterior
                print("chkconfig error when trying to add/delete service",
                      stderr)
            # FIXME: handle services with no chkconfig line and 
            # with no Default-Start levels in LSB header
            
                
            
        
        
