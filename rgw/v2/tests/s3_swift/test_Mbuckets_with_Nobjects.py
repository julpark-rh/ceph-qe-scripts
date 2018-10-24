# test basic creation of buckets with objects
import os, sys

sys.path.append(os.path.abspath(os.path.join(__file__, "../../../..")))
from v2.lib.resource_op import Config
import v2.lib.resource_op as s3lib
from v2.lib.s3.auth import Auth
import v2.utils.log as log
import v2.utils.utils as utils
from v2.utils.utils import RGWService
from v2.lib.rgw_config_opts import CephConfOp, ConfigOpts
from v2.utils.utils import HttpResponseParser
import traceback
import argparse
import yaml
import v2.lib.manage_data as manage_data
from v2.lib.exceptions import TestExecError
from v2.utils.test_desc import AddTestInfo
from v2.lib.s3.write_io_info import IOInfoInitialize, BasicIOInfoStructure
import time
import json
import time, hashlib

TEST_DATA_PATH = None
password = "32characterslongpassphraseneeded".encode('utf-8')
encryption_key = hashlib.md5(password).hexdigest()


def test_exec(config):
    test_info = AddTestInfo('create m buckets with n objects')
    io_info_initialize = IOInfoInitialize()
    basic_io_structure = BasicIOInfoStructure()
    io_info_initialize.initialize(basic_io_structure.initial())
    ceph_conf = CephConfOp()
    rgw_service = RGWService()

    try:

        test_info.started_info()

        # create user

        all_users_info = s3lib.create_users(config.user_count)

        if config.test_ops.get('encryption_algorithm', None) is not None:

            log.info('encryption enabled, making ceph config changes')

            ceph_conf.set_to_ceph_conf('global', ConfigOpts.rgw_crypt_require_ssl,
                                       False)

            srv_restarted = rgw_service.restart()

            time.sleep(30)

            if srv_restarted is False:
                raise TestExecError("RGW service restart failed")
            else:
                log.info('RGW service restarted')

        for each_user in all_users_info:

            # authenticate

            auth = Auth(each_user)

            if config.use_aws4 is True:
                rgw_conn = auth.do_auth(**{'signature_version': 's3v4'})
            else:
                rgw_conn = auth.do_auth()

            # enabling sharding

            if config.test_ops['sharding']['enable'] is True:

                log.info('enabling sharding on buckets')

                max_shards = config.test_ops['sharding']['max_shards']

                log.info('making changes to ceph.conf')

                ceph_conf.set_to_ceph_conf('global', ConfigOpts.rgw_override_bucket_index_max_shards,
                                           max_shards)

                log.info('trying to restart services ')

                srv_restarted = rgw_service.restart()

                time.sleep(10)

                if srv_restarted is False:
                    raise TestExecError("RGW service restart failed")
                else:
                    log.info('RGW service restarted')

            if config.test_ops['compression']['enable'] is True:

                    compression_type = config.test_ops['compression']['type']

                    log.info('enabling compression')

                    cmd = 'radosgw-admin zone placement modify --rgw-zone=default ' \
                          '--placement-id=default-placement --compression=%s' % compression_type

                    out = utils.exec_shell_cmd(cmd)

                    try:
                        data = json.loads(out)
                        if data['placement_pools'][0]['val']['compression'] == compression_type:
                            log.info('Compression enabled successfully')
                        else:
                            raise ValueError('failed to enable compression')
                    except ValueError, e:
                        exit(str(e))

                    log.info('trying to restart rgw services ')

                    srv_restarted = rgw_service.restart()

                    time.sleep(10)

                    if srv_restarted is False:
                        raise TestExecError("RGW service restart failed")
                    else:
                        log.info('RGW service restarted')

            # create buckets

            if config.test_ops['create_bucket'] is True:

                log.info('no of buckets to create: %s' % config.bucket_count)

                for bc in range(config.bucket_count):

                    bucket_name_to_create = utils.gen_bucket_name_from_userid(each_user['user_id'], rand_no=bc)

                    log.info('creating bucket with name: %s' % bucket_name_to_create)

                    # bucket = s3_ops.resource_op(rgw_conn, 'Bucket', bucket_name_to_create)

                    bucket = s3lib.resource_op({'obj': rgw_conn,
                                                'resource': 'Bucket',
                                                'args': [bucket_name_to_create]})

                    created = s3lib.resource_op({'obj': bucket,
                                                 'resource': 'create',
                                                 'args': None,
                                                 'extra_info': {'access_key': each_user['access_key']}})

                    if created is False:
                        raise TestExecError("Resource execution failed: bucket creation faield")

                    if created is not None:

                        response = HttpResponseParser(created)

                        if response.status_code == 200:
                            log.info('bucket created')

                        else:
                            raise TestExecError("bucket creation failed")

                    else:
                        raise TestExecError("bucket creation failed")

                    if config.test_ops['create_object'] is True:

                        # uploading data

                        log.info('s3 objects to create: %s' % config.objects_count)

                        for oc in range(config.objects_count):

                            s3_object_name = utils.gen_s3_object_name(bucket_name_to_create, oc)

                            log.info('s3 object name: %s' % s3_object_name)

                            s3_object_path = os.path.join(TEST_DATA_PATH, s3_object_name)

                            log.info('s3 object path: %s' % s3_object_path)

                            s3_object_size = utils.get_file_size(config.objects_size_range['min'],
                                                                 config.objects_size_range['max'])

                            data_info = manage_data.io_generator(s3_object_path, s3_object_size)

                            if data_info is False:
                                TestExecError("data creation failed")

                            log.info('uploading s3 object: %s' % s3_object_path)

                            upload_info = dict({'access_key': each_user['access_key']}, **data_info)

                            if config.test_ops.get('encryption_algorithm', None) is not None:

                                log.info('encryption enabled')

                                log.info('encryption algorithm: %s' % config.test_ops['encryption_algorithm'])

                                object_uploaded_status = s3lib.resource_op({'obj': bucket,
                                                                            'resource': 'put_object',
                                                                            'kwargs': dict(Body=open(s3_object_path),
                                                                                           Key=s3_object_name,
                                                                                           SSECustomerAlgorithm=
                                                                                           config.test_ops[
                                                                                               'encryption_algorithm'],
                                                                                           SSECustomerKey=encryption_key
                                                                                           ),
                                                                            'extra_info': upload_info})


                            else:

                                object_uploaded_status = s3lib.resource_op({'obj': bucket,
                                                                            'resource': 'upload_file',
                                                                            'args': [s3_object_path, s3_object_name],
                                                                            'extra_info': upload_info})

                            if object_uploaded_status is False:
                                raise TestExecError("Resource execution failed: object upload failed")

                            if object_uploaded_status is None:
                                log.info('object uploaded')

                            if config.test_ops['download_object'] is True:

                                log.info('trying to download object: %s' % s3_object_name)

                                s3_object_download_name = s3_object_name + "." + "download"

                                s3_object_download_path = os.path.join(TEST_DATA_PATH, s3_object_download_name)

                                log.info('s3_object_download_path: %s' % s3_object_download_path)

                                log.info('downloading to filename: %s' % s3_object_download_name)

                                if config.test_ops.get('encryption_algorithm', None) is not None:

                                    log.info('encryption download')

                                    log.info('encryption algorithm: %s' % config.test_ops['encryption_algorithm'])

                                    object_downloaded_status = bucket.download_file(s3_object_name, s3_object_download_path,
                                                        ExtraArgs={'SSECustomerKey': encryption_key,
                                                                   'SSECustomerAlgorithm': config.test_ops['encryption_algorithm'] })

                                else:

                                    object_downloaded_status = s3lib.resource_op({'obj': bucket,
                                                                                  'resource': 'download_file',
                                                                                  'args': [s3_object_name,
                                                                                           s3_object_download_path],
                                                                                  })

                                if object_downloaded_status is False:
                                    raise TestExecError("Resource execution failed: object download failed")

                                if object_downloaded_status is None:
                                    log.info('object downloaded')

                        # verification of shards after upload

                        if config.test_ops['sharding']['enable'] is True:
                            cmd = 'radosgw-admin metadata get bucket:%s | grep bucket_id' % bucket.name

                            out = utils.exec_shell_cmd(cmd)

                            b_id = out.replace('"', '').strip().split(":")[1].strip().replace(',', '')

                            cmd2 = 'rados -p default.rgw.buckets.index ls | grep %s' % b_id

                            out = utils.exec_shell_cmd(cmd2)

                            log.info('got output from sharing verification.--------')

                        # print out bucket stats and verify in logs for compressed data by
                        # comparing size_kb_utilized and size_kb_actual

                        if config.test_ops['compression']['enable'] is True:

                            cmd = 'radosgw-admin bucket stats --bucket=%s' % bucket.name

                            out = utils.exec_shell_cmd(cmd)

                        if config.test_ops['delete_bucket_object'] is True:

                            log.info('listing all objects in bucket: %s' % bucket.name)

                            # objects = s3_ops.resource_op(bucket, 'objects', None)
                            objects = s3lib.resource_op({'obj': bucket,
                                                         'resource': 'objects',
                                                         'args': None})

                            log.info('objects :%s' % objects)

                            # all_objects = s3_ops.resource_op(objects, 'all')
                            all_objects = s3lib.resource_op({'obj': objects,
                                                             'resource': 'all',
                                                             'args': None})

                            log.info('all objects: %s' % all_objects)

                            for obj in all_objects:
                                log.info('object_name: %s' % obj.key)

                            log.info('deleting all objects in bucket')

                            # objects_deleted = s3_ops.resource_op(objects, 'delete')

                            objects_deleted = s3lib.resource_op({'obj': objects,
                                                                 'resource': 'delete',
                                                                 'args': None})

                            log.info('objects_deleted: %s' % objects_deleted)

                            if objects_deleted is False:
                                raise TestExecError('Resource execution failed: Object deletion failed')

                            if objects_deleted is not None:

                                response = HttpResponseParser(objects_deleted[0])

                                if response.status_code == 200:
                                    log.info('objects deleted ')

                                else:
                                    raise TestExecError("objects deletion failed")

                            else:
                                raise TestExecError("objects deletion failed")

                            log.info('deleting bucket: %s' % bucket.name)

                            # bucket_deleted_status = s3_ops.resource_op(bucket, 'delete')

                            bucket_deleted_status = s3lib.resource_op({'obj': bucket,
                                                                       'resource': 'delete',
                                                                       'args': None})

                            log.info('bucket_deleted_status: %s' % bucket_deleted_status)

                            if bucket_deleted_status is not None:

                                response = HttpResponseParser(bucket_deleted_status)

                                if response.status_code == 204:
                                    log.info('bucket deleted ')

                                else:
                                    raise TestExecError("bucket deletion failed")

                            else:
                                raise TestExecError("bucket deletion failed")

            # disable compression after test

            if config.test_ops['compression']['enable'] is True:

                log.info('disable compression')

                cmd = 'radosgw-admin zone placement modify --rgw-zone=default ' \
                      '--placement-id=default-placement --compression='

                out = utils.exec_shell_cmd(cmd)

                srv_restarted = rgw_service.restart()

                time.sleep(10)

                if srv_restarted is False:
                    raise TestExecError("RGW service restart failed")
                else:
                    log.info('RGW service restarted')

        test_info.success_status('test passed')

        sys.exit(0)

    except Exception, e:
        log.info(e)
        log.info(traceback.format_exc())
        test_info.failed_status('test failed')
        sys.exit(1)

    except TestExecError, e:
        log.info(e)
        log.info(traceback.format_exc())
        test_info.failed_status('test failed')
        sys.exit(1)


if __name__ == '__main__':

    project_dir = os.path.abspath(os.path.join(__file__, "../../.."))
    test_data_dir = 'test_data'

    ceph_conf = CephConfOp()
    rgw_service = RGWService()

    TEST_DATA_PATH = (os.path.join(project_dir, test_data_dir))

    log.info('TEST_DATA_PATH: %s' % TEST_DATA_PATH)

    if not os.path.exists(TEST_DATA_PATH):
        log.info('test data dir not exists, creating.. ')
        os.makedirs(TEST_DATA_PATH)

    parser = argparse.ArgumentParser(description='RGW S3 Automation')

    parser.add_argument('-c', dest="config",
                        help='RGW Test yaml configuration')

    args = parser.parse_args()

    yaml_file = args.config
    config = Config()
    config.shards = None
    config.max_objects = None
    with open(yaml_file, 'r') as f:
        doc = yaml.load(f)
    config.user_count = doc['config']['user_count']
    config.bucket_count = doc['config']['bucket_count']
    config.objects_count = doc['config']['objects_count']
    config.use_aws4 = doc['config'].get('use_aws4', None)
    config.objects_size_range = {'min': doc['config']['objects_size_range']['min'],
                                 'max': doc['config']['objects_size_range']['max']}

    config.test_ops = doc['config']['test_ops']

    log.info('user_count:%s\n'
             'bucket_count: %s\n'
             'objects_count: %s\n'
             'objects_size_range: %s\n'
             % (config.user_count, config.bucket_count, config.objects_count, config.objects_size_range))

    log.info('test_ops: %s' % config.test_ops)

    test_exec(config)