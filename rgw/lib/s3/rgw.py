from auth import Authenticate
from bucket import Bucket
from objects import KeyOp, PutContentsFromFile, PutContentsFromString, MultipartPut
import utils.log as log
import utils.utils as utils
from random import randint
import os


class BaseOp(object):

    def __init__(self, access_key, secret_key):

        log.debug('class: %s' % self.__class__.__name__)

        auth = Authenticate(access_key, secret_key)
        connection = auth.do_auth()

        assert connection['status']
        connection = connection['conn']

        self.bucket = Bucket(connection)


class RGW(BaseOp):

    def __init__(self, access_key, secret_key):

        super(RGW, self).__init__(access_key, secret_key)

    def create_bucket_with_keys(self, bucket_create_nos, object_create_nos, **object_size):

        min_object_size = object_size['min']
        max_object_size = object_size['max']

        self.buckets_created = []

        log.info('no of buckets to create: %s' % bucket_create_nos)
        log.info('no of obejcts in a bucket to create %s' % object_create_nos)

        for bucket_no in range(bucket_create_nos):

            log.debug('iter: %s' % bucket_no)

            bucket_name = str('buckey') + "." + str(bucket_no)

            log.info('bucket_name: %s' % bucket_name)

            bucket_created = self.bucket.create(bucket_name)

            if not bucket_created['status']:
                raise AssertionError

            log.info('bucket created')

            self.buckets_created.append(bucket_name)

            if object_create_nos > 0:

                log.info('objects min size: %s' % min_object_size)
                log.info('objects max size: %s' % max_object_size)

                for key in range(object_create_nos):

                    key_name = str("key") + "." + str(key)

                    log.info('key name to create %s' % key_name)

                    size = randint(min_object_size, max_object_size)

                    log.info('size of the file to create %s' % size)

                    random_file, md5 = utils.create_file(key_name, size)

                    key_op = KeyOp(bucket_created['bucket'])

                    key_created = key_op.create(key_name)

                    if key_created is None:
                        raise AssertionError

                    log.info('key created')

                    put_file = PutContentsFromFile(key_created)

                    log.info('\nrandom filename created :%s\n md5 of the file: %s' % (random_file, md5))

                    put = put_file.put(random_file)

                    if not put['status']:
                        raise AssertionError

                    log.info('put of the file completed')

                    key_on_rgw_node = key_op.get(key_name)

                    log.info('key on RGW %s\n' % key_on_rgw_node)

    def delete_bucket_with_keys(self):

        log.info('deleted buckets with keys')

        for bucket_name in self.buckets_created:

            log.info('ops on bucket name: %s' % bucket_name)

            bucket = self.bucket.get(bucket_name)

            all_keys_in_bucket = bucket['bucket'].list()

            if all_keys_in_bucket:

                log.info('got all keys in bucket: %s' % all_keys_in_bucket)

                key_op = KeyOp(bucket['bucket'])

                log.info('delete of all keys')

                keys_deleted = key_op.multidelete_keys(all_keys_in_bucket)

                if keys_deleted is None:
                    log.error('key not deleted')
                    raise AssertionError

                log.info('all keys deleted')

                log.info('delete of bucket')

                bucket_deleted = self.bucket.delete(bucket_name)

                if not bucket_deleted['status']:
                    log.error('bucket not deleted')
                    raise AssertionError

                log.info('bucket deleted')


class RGWMultpart(BaseOp):

    def __init__(self, access_key, secret_key):

        super(RGWMultpart, self).__init__(access_key, secret_key)

        self.set_cancel_upload = False

        self.break_upload_at_part_no = 0

    def upload(self, size, bucket_name):

            bucket_created = self.bucket.create(bucket_name)

            if not bucket_created['status']:
                raise AssertionError

            log.info('bucket created')

            log.info('multpart upload enabled')

            log.info('size of the file to create %s' % size)

            key_name = bucket_name + "." + "mpFile"

            filename, md5 = utils.create_file(key_name, size)

            json_file = os.path.join(os.path.dirname(filename), "_json.json")

            multipart = MultipartPut(bucket_created['bucket'], filename, json_file)

            multipart.break_at_part_no = self.break_upload_at_part_no

            multipart.iniate_multipart()
            put = multipart.put()

            if not put['status']:
                raise AssertionError

            if not self.set_cancel_upload:

                if not multipart.complete_multipart():
                    raise AssertionError

            else:

                if not multipart.cancel_multpart():
                    raise AssertionError
