import os
import random
import cinderclient.exceptions as c_exceptions
from cinderclient.v2 import client as c_client
import log
import time


class CinderReturnStack(object):
    def __init__(self):
        pass


class CinderAuth(object):

    def __init__(self):
        self.os_username = os.environ['OS_USERNAME']
        self.os_api_key = os.environ['OS_PASSWORD']
        self.os_auth_url = os.environ['OS_AUTH_URL']
        self.os_tenant = os.environ['OS_TENANT_NAME']

    def auth(self):

        """

        :return:auth_stack
                - auth_stack.cinder : cinder object after authenticating
                - auth_stack.status : True or False

        """

        auth_stack = CinderReturnStack()

        log.info('in lib: auth')

        try:
            cinder = c_client.Client(auth_url=self.os_auth_url, username=self.os_username, api_key=self.os_api_key,
                                     project_id=self.os_tenant, service_type='volumev2')
            #cinder.volumes.delete()

            auth_stack.cinder, auth_stack.status = cinder, True

            log.info('Cinder Auth successful')

        except c_exceptions.AuthorizationFailure, e:
            auth_stack.cinder, auth_stack.status = None, False
            log.error('cinder auth failed')
            log.error(e.message)

        return auth_stack


class CinderVolumes(object):

    def __init__(self, cinder_auth):
        self.cinder = cinder_auth

    def create_volume(self, name, size, image_id=None):

        """
        :param name: string
        :param size: int
        :param image_id: int[optional]
        :return volume_create
                - volume_create.vol     : volume object
                - volume_create.status  : True or False
        """

        log.info("in lib: Create volume")

        volume_create = CinderReturnStack()

        try:
            log.info('initialized volume creation')
            volume = self.cinder.volumes.create(name=name, size=size, imageRef=image_id)
            volume_create.vol,volume_create.status = volume, True

        except c_exceptions.ClientException,e:
            log.error(e)
            volume_create.vol, volume_create.status = None, False

        return volume_create

    def list_volumes(self):

        """
        :return volumes_list
                - volumes_list.volumes : list of volumes object
                - volumes_list.status  : True or False
        """

        volumes_list = CinderReturnStack()
        volumes_list.volumes = []
        try:
            log.info("List cinder volumes")
            volumes = self.cinder.volumes.list()

            # will return volumes.size, volumes.name , volumes.id, volumes.status ...

            volumes_list.status = True
            if volumes:
                volumes_list.volumes = volumes

        except (c_exceptions.NotFound,c_exceptions.ClientException),  e:
            log.error(e)
            volumes_list.status = False

        return volumes_list

    def get_volume(self,volume):

        """

        :param volume_id: volume object
        :return:each_volume
                - each_volume.volume : volume object
                - each_volume.status : True or False

        """

        each_volume = CinderReturnStack()
        each_volume.volume = None
        try:
            log.info("get cinder volume details")
            volume = self.cinder.volumes.get(volume.id)
            each_volume.volume = volume
            each_volume.status = True

        except (c_exceptions.NotFound,c_exceptions.ClientException),  e:
            log.error(e)
            each_volume.status = False

        return each_volume

    def extend_volume(self, volume, new_size):

        """
        :param volume:
        :param new_size:
        :return extend
                - extend.execute : True or False
        """

        extend = CinderReturnStack()
        extend.execute = False

        try:
            self.cinder.volumes.extend(volume, new_size)
            extend.execute = True

        except c_exceptions.ClientException, e:
            log.error(e)

        return extend

    def delete_volume(self, volume):

        """

        :param volume: volume object
        :return: volume_delete
                 - volume_delete.execute: True or False
        """

        log.info('in lib of delete volume')
        volume_delete = CinderReturnStack()
        volume_delete.execute = False

        try:
            self.cinder.volumes.delete(volume)
            volume_delete.execute = True
            log.info('delete volume executed')
        except (c_exceptions.NotFound, c_exceptions.ClientException), e:
            log.error(e)

        return volume_delete


class CinderBackup(object):

    def __init__(self, cinder_auth):
        self.cinder = cinder_auth

    def create_backup(self, volume, incremental=False, name=None):

        """
        :param volume: volume object
        :param incremental: int
        :param name: string
        :return backup
                - backup.volume_backup : volume backup object
                - backup.status        : True or False
        """

        backup = CinderReturnStack()
        backup.volume_backup = None
        try:
            volume_backup = self.cinder.backups.create(volume, name=name, incremental=incremental)
            backup.volume_backup,backup.status = volume_backup, True

        except c_exceptions.ClientException,e :
            log.error(e)
            backup.status = False

        return backup

    def list_backup(self):

        """
        :return backups_list
                - backups_list.backups : list of backup objects
                - backups_list.status  : True or False

        """

        backups_list = CinderReturnStack()
        backups_list.backups = []
        try:
            log.info("List cinder backup volumes")
            backups = self.cinder.backups.list()

            # will return backups class.

            backups_list.status = True
            if backups:
                backups_list.backups = backups

        except (c_exceptions.NotFound,c_exceptions.ClientException ),  e:
            log.error(e)
            backups_list.status = False

        return backups_list

    def delete_backup(self, backup):

        """

        :param backup: object of the backup
        :return: delete
                 - delete.execue: True or False
        """

        delete = CinderReturnStack()
        delete.execute = False
        try:
            self.cinder.backups.delete(backup)
            delete.execute = True
        except (c_exceptions.NotFound, c_exceptions.ClientException), e:
            log.error(e)

        return delete


class CinderSnapshot(object):

    def __init__(self,cinder_auth):
        self.cinder = cinder_auth

    def create_snapshot(self, volume, snapshot_name):

        """
        :param volume: object of the volume
        :param snapshot_name: string, name for creating the snapshot
        :return snapshot
                - snapshot.volume_snapshot  : object of the snapshot
                - snapshot.status           : True or False
        """


        log.info('in lib: create snapshots')

        snapshot = CinderReturnStack()
        snapshot.volume_snapshot = None
        ftype = False

        if volume.status == "available":
            ftype = False

        elif volume.status == "in-use":
            ftype = True

        log.info('setting force type: %s' % ftype)

        try:
            volume_snapshot = self.cinder.volume_snapshots.create(volume, name=snapshot_name, force=ftype)
            snapshot.volume_snapshot = volume_snapshot
            snapshot.status = True
            log.info('volume snapshot creation executed')
        except c_exceptions.ClientException,e:
            log.error(e)
            snapshot.status = False

        return snapshot

    def list_snapshot(self):

        """

        :return:snapshot_list
                - snapshot_list.snapshots   : lists of snapshot objects
                - snapshot_list.status      : True or False

        """

        log.info('in lib of list snapshot')

        snapshots_list = CinderReturnStack()
        snapshots_list.snapshots = []

        try:
            snapshots = self.cinder.volume_snapshots.list()
            # will return snapshot class.

            snapshots_list.status = True
            if snapshots:
                log.info('got snapshots')
                snapshots_list.snapshots = snapshots

            log.error('got no snapshots')

        except (c_exceptions.NotFound, c_exceptions.ClientException),  e:
            log.error(e)
            snapshots_list.status = False

        return snapshots_list

    def delete_snapshot(self, snapshot):

        """

        :param snapshot: object of the snapshot
        :return:snapshot_delete
                - snapshot_delete.execute: True or False
        """

        log.info('in lib of delete snapshot')
        snapshot_delete = CinderReturnStack()
        snapshot_delete.execute = False
        try:
            self.cinder.volume_snapshots.delete(snapshot)
            snapshot_delete.execute = True
            log.info('delete snapshot executed')
        except (c_exceptions.NotFound, c_exceptions.ClientException), e:
            log.error(e)

        return snapshot_delete

    def create_vol_from_snap(self, snapshot, size):

        """

        :param snapshot: object of the snapshot
        :param size: int,
        :return: snapshot_volume
                 - snapshot_volume.status: True or False
        """

        log.info('in lib of create vol from snapshot')

        snapshot_volume = CinderReturnStack()
        snapshot_volume.volume = None

        try:
            volume = self.cinder.volumes.create(size=size, snapshot_id=snapshot)
            snapshot_volume.status = True
            snapshot_volume.volume = volume
            log.info('snapshot volume created')
        except c_exceptions.ClientException, e:
            log.error(e)
            snapshot_volume.status = False

        return snapshot_volume


