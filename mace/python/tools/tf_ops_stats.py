import argparse
import sys
import six
import tensorflow as tf
from tensorflow import gfile

# ./bazel-bin/mace/python/tools/tf_ops_stats --input model.pb

FLAGS = None

def hist_inc(hist, key):
  if key in hist:
    hist[key] += 1
  else:
    hist[key] = 1

def to_int_list(long_list):
  int_list = []
  for value in long_list:
    int_list.append(int(value))
  return int_list

def main(unused_args):
  if not FLAGS.input or not gfile.Exists(FLAGS.input):
    print('Input graph file ' + FLAGS.input + ' does not exist!')
    return -1

  input_graph_def = tf.GraphDef()
  with gfile.Open(FLAGS.input, 'rb') as f:
    data = f.read()
    input_graph_def.ParseFromString(data)

  with tf.Session() as session:
    with session.graph.as_default() as graph:
      tf.import_graph_def(input_graph_def, name='')
  
    stats = {}
    ops = graph.get_operations()
    # extract kernel size for conv_2d
    tensor_shapes = {}
    tensor_values = {}
    for op in ops:
      if op.type == 'Const':
        for output in op.outputs:
          tensor_name = output.name
          tensor = output.eval()
          tensor_shape = list(tensor.shape)
          tensor_shapes[tensor_name] = tensor_shape
          if len(tensor_shape) == 1 and tensor_shape[0] < 10:
            tensor_values[tensor_name] = list(tensor)

    for op in ops:
      if op.type in ['Conv2D']:
        padding = op.get_attr('padding')
        strides = to_int_list(op.get_attr('strides'))
        data_format = op.get_attr('data_format')
        ksize = 'Unknown'
        for input in op.inputs:
          input_name = input.name
          if input_name.endswith('weights/read:0'):
            ksize = input.shape.as_list()
            break
          if input_name.endswith('weights:0') and input_name in tensor_shapes:
            ksize = tensor_shapes[input_name]
            break
        key = '%s(padding=%s, strides=%s, ksize=%s, format=%s)' % (op.type, padding, strides, ksize, data_format)
        hist_inc(stats, key)
      elif op.type in ['FusedResizeAndPadConv2D']:
        padding = op.get_attr('padding')
        strides = to_int_list(op.get_attr('strides'))
        resize_align_corners = op.get_attr('resize_align_corners')
        ksize = 'Unknown'
        for input in op.inputs:
          input_name = input.name
          if input_name.endswith('weights:0') and input_name in tensor_shapes:
            ksize = tensor_shapes[input_name]
            break
        key = '%s(padding=%s, strides=%s, ksize=%s, resize_align_corners=%s)' % (op.type, padding, strides, ksize, resize_align_corners)
        hist_inc(stats, key)
      elif op.type in ['ResizeBilinear']:
        align_corners = op.get_attr('align_corners')
        size = 'Unknown'
        for input in op.inputs:
          input_name = input.name
          if input_name.endswith('size:0') and input_name in tensor_values:
            size = tensor_values[input_name]
            break
        key = '%s(size=%s, align_corners=%s)' % (op.type, size, align_corners)
        hist_inc(stats, key)
      elif op.type in ['AvgPool', 'MaxPool']:
        padding = op.get_attr('padding')
        strides = to_int_list(op.get_attr('strides'))
        ksize = to_int_list(op.get_attr('ksize'))
        data_format = op.get_attr('data_format')
        key = '%s(padding=%s, strides=%s, ksize=%s)' % (op.type, padding, strides, ksize)
        hist_inc(stats, key)
      elif op.type in ['SpaceToBatchND', 'BatchToSpaceND']:
        block_shape = 'Unknown'
        for input in op.inputs:
          input_name = input.name
          if input_name.endswith('block_shape:0') and input_name in tensor_values:
            block_shape = tensor_values[input_name]
            break
        paddings = 'Unknown'
        for input in op.inputs:
          input_name = input.name
          if input_name.endswith('paddings:0') and input_name in tensor_values:
            paddings = tensor_values[input_name]
            break
        crops = 'Unknown'
        for input in op.inputs:
          input_name = input.name
          if input_name.endswith('crops:0') and input_name in tensor_values:
            paddings = tensor_values[input_name]
            break
        if op.type == 'SpaceToBatchND':
          key = '%s(block_shape=%s, paddings=%s)' % (op.type, block_shape, paddings)
        else:
          key = '%s(block_shape=%s, crops=%s)' % (op.type, block_shape, crops)
        hist_inc(stats, key)
      elif op.type == 'Pad':
        paddings = 'Unknown'
        for input in op.inputs:
          input_name = input.name
          if input_name.endswith('paddings:0') and input_name in tensor_values:
            paddings = tensor_values[input_name]
            break
        key = '%s(paddings=%s)' % (op.type, paddings)
        hist_inc(stats, key)
      else:
        hist_inc(stats, op.type)
  
  for key, value in sorted(six.iteritems(stats)):
    print('%s: %d' % (key, value))

def parse_args():
  '''Parses command line arguments.'''
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '--input',
    type=str,
    default='',
    help='TensorFlow \'GraphDef\' file to load.')
  return parser.parse_known_args()

if __name__ == '__main__':
  FLAGS, unparsed = parse_args()
  main(unused_args=[sys.argv[0]] + unparsed)
