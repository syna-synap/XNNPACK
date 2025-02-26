#!/usr/bin/env python
# Copyright 2021 Google LLC
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import codecs
import math
import os
import re
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xngen
import xnncommon


parser = argparse.ArgumentParser(
  description='Vector conversion operation microkernel test generator')
parser.add_argument("-s", "--spec", metavar="FILE", required=True,
                    help="Specification (YAML) file")
parser.add_argument("-o", "--output", metavar="FILE", required=True,
                    help='Output (C++ source) file')
parser.set_defaults(defines=list())


def split_ukernel_name(name):
  match = re.fullmatch(r"xnn_(f16|f32|qs16|qs8|qu8)(_(f16|f32|qs8|qu8))?_vcvt_ukernel__(.+)_x(\d+)", name)
  if match is None:
    raise ValueError("Unexpected microkernel name: " + name)

  input_datatype = match.group(1)
  if match.group(2):
    output_datatype = match.group(3)
  else:
    output_datatype = input_datatype

  batch_tile = int(match.group(5))

  arch, isa, assembly = xnncommon.parse_target_name(target_name=match.group(4))
  return input_datatype, output_datatype, batch_tile, arch, isa


CVT_TEST_TEMPLATE = """\
TEST(${TEST_NAME}, batch_eq_${BATCH_TILE}) {
  $if ISA_CHECK:
    ${ISA_CHECK};
  VCvtMicrokernelTester()
    .batch_size(${BATCH_TILE})
    $if INPUT_DATATYPE == "QS16":
      .input_zero_point(0)
    $if OUTPUT_DATATYPE == "QS8":
      .qmin(std::numeric_limits<int8_t>::min())
      .qmax(std::numeric_limits<int8_t>::max())
    $elif OUTPUT_DATATYPE == "QU8":
      .qmin(std::numeric_limits<uint8_t>::min())
      .qmax(std::numeric_limits<uint8_t>::max())
    .Test(${", ".join(TEST_ARGS)});
}

$if BATCH_TILE > 1:
  TEST(${TEST_NAME}, batch_div_${BATCH_TILE}) {
    $if ISA_CHECK:
      ${ISA_CHECK};
    for (size_t batch_size = ${BATCH_TILE*2}; batch_size < ${BATCH_TILE*10}; batch_size += ${BATCH_TILE}) {
      VCvtMicrokernelTester()
        .batch_size(batch_size)
        $if INPUT_DATATYPE == "QS16":
          .input_zero_point(0)
        $if OUTPUT_DATATYPE == "QS8":
          .qmin(std::numeric_limits<int8_t>::min())
          .qmax(std::numeric_limits<int8_t>::max())
        $elif OUTPUT_DATATYPE == "QU8":
          .qmin(std::numeric_limits<uint8_t>::min())
          .qmax(std::numeric_limits<uint8_t>::max())
        .Test(${", ".join(TEST_ARGS)});
    }
  }

  TEST(${TEST_NAME}, batch_lt_${BATCH_TILE}) {
    $if ISA_CHECK:
      ${ISA_CHECK};
    for (size_t batch_size = 1; batch_size < ${BATCH_TILE}; batch_size++) {
      VCvtMicrokernelTester()
        .batch_size(batch_size)
        $if INPUT_DATATYPE == "QS16":
          .input_zero_point(0)
        $if OUTPUT_DATATYPE == "QS8":
          .qmin(std::numeric_limits<int8_t>::min())
          .qmax(std::numeric_limits<int8_t>::max())
        $elif OUTPUT_DATATYPE == "QU8":
          .qmin(std::numeric_limits<uint8_t>::min())
          .qmax(std::numeric_limits<uint8_t>::max())
        .Test(${", ".join(TEST_ARGS)});
    }
  }

TEST(${TEST_NAME}, batch_gt_${BATCH_TILE}) {
  $if ISA_CHECK:
    ${ISA_CHECK};
  for (size_t batch_size = ${BATCH_TILE+1}; batch_size < ${10 if BATCH_TILE == 1 else BATCH_TILE*2}; batch_size++) {
    VCvtMicrokernelTester()
      .batch_size(batch_size)
      $if INPUT_DATATYPE == "QS16":
        .input_zero_point(0)
      $if OUTPUT_DATATYPE == "QS8":
        .qmin(std::numeric_limits<int8_t>::min())
        .qmax(std::numeric_limits<int8_t>::max())
      $elif OUTPUT_DATATYPE == "QU8":
        .qmin(std::numeric_limits<uint8_t>::min())
        .qmax(std::numeric_limits<uint8_t>::max())
      .Test(${", ".join(TEST_ARGS)});
  }
}

$if INPUT_DATATYPE.startswith("Q") or OUTPUT_DATATYPE.startswith("Q"):
  TEST(${TEST_NAME}, scale) {
    $if ISA_CHECK:
      ${ISA_CHECK};
    for (size_t batch_size = 1; batch_size <= ${BATCH_TILE*5}; batch_size += ${max(1, BATCH_TILE-1)}) {
      VCvtMicrokernelTester()
        .batch_size(batch_size)
        .scale(50)
        $if INPUT_DATATYPE == "QS16":
          .input_zero_point(0)
        $if OUTPUT_DATATYPE == "QS8":
          .qmin(std::numeric_limits<int8_t>::min())
          .qmax(std::numeric_limits<int8_t>::max())
        $elif OUTPUT_DATATYPE == "QU8":
          .output_zero_point(100)
          .qmin(std::numeric_limits<uint8_t>::min())
          .qmax(std::numeric_limits<uint8_t>::max())
        .Test(${", ".join(TEST_ARGS)});
    }
  }

$if INPUT_DATATYPE in ["QS8", "QU8"]:
  TEST(${TEST_NAME}, input_zero_point) {
    $if ISA_CHECK:
      ${ISA_CHECK};
    for (int16_t input_zero_point = 0; input_zero_point < 5; input_zero_point += 2) {
      for (size_t batch_size = 1; batch_size <= ${BATCH_TILE*5}; batch_size += ${max(1, BATCH_TILE-1)}) {
        VCvtMicrokernelTester()
          .batch_size(batch_size)
          .input_zero_point(input_zero_point)
          $if OUTPUT_DATATYPE == "QS8":
            .qmin(std::numeric_limits<int8_t>::min())
            .qmax(std::numeric_limits<int8_t>::max())
          $elif OUTPUT_DATATYPE == "QU8":
            .qmin(std::numeric_limits<uint8_t>::min())
            .qmax(std::numeric_limits<uint8_t>::max())
          .Test(${", ".join(TEST_ARGS)});
      }
    }
  }

$if OUTPUT_DATATYPE in ["QS8", "QU8"]:
  TEST(${TEST_NAME}, output_zero_point) {
    $if ISA_CHECK:
      ${ISA_CHECK};
    for (int16_t output_zero_point = 0; output_zero_point < 5; output_zero_point += 2) {
      for (size_t batch_size = 1; batch_size <= ${BATCH_TILE*5}; batch_size += ${max(1, BATCH_TILE-1)}) {
        VCvtMicrokernelTester()
          .batch_size(batch_size)
          $if INPUT_DATATYPE == "QS16":
            .input_zero_point(0)
          .output_zero_point(output_zero_point)
          $if OUTPUT_DATATYPE == "QS8":
            .qmin(std::numeric_limits<int8_t>::min())
            .qmax(std::numeric_limits<int8_t>::max())
          $elif OUTPUT_DATATYPE == "QU8":
            .qmin(std::numeric_limits<uint8_t>::min())
            .qmax(std::numeric_limits<uint8_t>::max())
          .Test(${", ".join(TEST_ARGS)});
      }
    }
  }

  $if INPUT_DATATYPE == "F32":
    TEST(${TEST_NAME}, saturation) {
      $if ISA_CHECK:
        ${ISA_CHECK};
      for (size_t batch_size = 1; batch_size <= ${BATCH_TILE*5}; batch_size += ${max(1, BATCH_TILE-1)}) {
        VCvtMicrokernelTester()
          .batch_size(batch_size)
          .scale(500)
          $if OUTPUT_DATATYPE == "QS8":
            .qmin(std::numeric_limits<int8_t>::min())
            .qmax(std::numeric_limits<int8_t>::max())
          $elif OUTPUT_DATATYPE == "QU8":
            .output_zero_point(128)
            .qmin(std::numeric_limits<uint8_t>::min())
            .qmax(std::numeric_limits<uint8_t>::max())
          .Test(${", ".join(TEST_ARGS)});
      }
    }

    TEST(${TEST_NAME}, overflow) {
      $if ISA_CHECK:
        ${ISA_CHECK};
      for (size_t batch_size = 1; batch_size <= ${BATCH_TILE*5}; batch_size += ${max(1, BATCH_TILE-1)}) {
        VCvtMicrokernelTester()
          .batch_size(batch_size)
          .scale(4294967296.0f)
          $if INPUT_DATATYPE == "QS16":
            .input_zero_point(0)
          $if OUTPUT_DATATYPE == "QS8":
            .qmin(std::numeric_limits<int8_t>::min())
            .qmax(std::numeric_limits<int8_t>::max())
          $elif OUTPUT_DATATYPE == "QU8":
            .qmin(std::numeric_limits<uint8_t>::min())
            .qmax(std::numeric_limits<uint8_t>::max())
          .Test(${", ".join(TEST_ARGS)});
      }
    }

$if INPUT_DATATYPE == "F32" and OUTPUT_DATATYPE == "QS8":
  TEST(${TEST_NAME}, qmin) {
    $if ISA_CHECK:
      ${ISA_CHECK};
    for (int16_t qmin = -128; qmin < 127; qmin += 51) {
      for (size_t batch_size = 1; batch_size <= ${BATCH_TILE*5}; batch_size += ${max(1, BATCH_TILE-1)}) {
        VCvtMicrokernelTester()
          .batch_size(batch_size)
          .scale(500)
          .qmin(qmin)
          .qmax(std::numeric_limits<int8_t>::max())
          .Test(${", ".join(TEST_ARGS)});
      }
    }
  }

  TEST(${TEST_NAME}, qmax) {
    $if ISA_CHECK:
      ${ISA_CHECK};
    for (int16_t qmax = -127; qmax <= 127; qmax += 51) {
      for (size_t batch_size = 1; batch_size <= ${BATCH_TILE*5}; batch_size += ${max(1, BATCH_TILE-1)}) {
        VCvtMicrokernelTester()
          .batch_size(batch_size)
          .scale(500)
          $if INPUT_DATATYPE == "QS16":
            .input_zero_point(0)
          .qmin(std::numeric_limits<int8_t>::min())
          .qmax(qmax)
          .Test(${", ".join(TEST_ARGS)});
      }
    }
  }

$if INPUT_DATATYPE == "F32" and OUTPUT_DATATYPE == "QU8":
  TEST(${TEST_NAME}, qmin) {
    $if ISA_CHECK:
      ${ISA_CHECK};
    for (int16_t qmin = 0; qmin < 255; qmin += 51) {
      for (size_t batch_size = 1; batch_size <= ${BATCH_TILE*5}; batch_size += ${max(1, BATCH_TILE-1)}) {
        VCvtMicrokernelTester()
          .batch_size(batch_size)
          .scale(500)
          .output_zero_point(128)
          .qmin(qmin)
          .qmax(std::numeric_limits<uint8_t>::max())
          .Test(${", ".join(TEST_ARGS)});
      }
    }
  }

  TEST(${TEST_NAME}, qmax) {
    $if ISA_CHECK:
      ${ISA_CHECK};
    for (int16_t qmax = 1; qmax <= 255; qmax += 51) {
      for (size_t batch_size = 1; batch_size <= ${BATCH_TILE*5}; batch_size += ${max(1, BATCH_TILE-1)}) {
        VCvtMicrokernelTester()
          .batch_size(batch_size)
          .scale(500)
          .output_zero_point(128)
          .qmin(std::numeric_limits<uint8_t>::min())
          .qmax(qmax)
          .Test(${", ".join(TEST_ARGS)});
      }
    }
  }
"""


def generate_test_cases(ukernel, init_fn, input_datatype, output_datatype,
                        batch_tile, isa):
  """Generates all tests cases for a Vector Convert Operation micro-kernel.

  Args:
    ukernel: C name of the micro-kernel function.
    init_fn: C name of the function to initialize microkernel parameters.
    input_datatype: input conversion data type.
    output_datatype: output conversion data type.
    batch_tile: Number of batch elements processed per one iteration of the
                inner loop of the micro-kernel.
    isa: instruction set required to run the micro-kernel. Generated unit test
         will skip execution if the host processor doesn't support this ISA.

  Returns:
    Code for the test case.
  """
  _, test_name = ukernel.split("_", 1)
  test_args = [ukernel]
  if init_fn:
    test_args.append(init_fn)
  return xngen.preprocess(CVT_TEST_TEMPLATE, {
      "TEST_NAME": test_name.upper().replace("UKERNEL_", ""),
      "TEST_ARGS": test_args,
      "BATCH_TILE": batch_tile,
      "INPUT_DATATYPE": input_datatype.upper(),
      "OUTPUT_DATATYPE": output_datatype.upper(),
      "ISA_CHECK": xnncommon.generate_isa_check_macro(isa),
    })


def main(args):
  options = parser.parse_args(args)

  with codecs.open(options.spec, "r", encoding="utf-8") as spec_file:
    spec_yaml = yaml.safe_load(spec_file)
    if not isinstance(spec_yaml, list):
      raise ValueError("expected a list of micro-kernels in the spec")

    tests = """\
// Copyright 2021 Google LLC
//
// This source code is licensed under the BSD-style license found in the
// LICENSE file in the root directory of this source tree.
//
// Auto-generated file. Do not edit!
//   Specification: {specification}
//   Generator: {generator}


#include <gtest/gtest.h>

#include <xnnpack/common.h>
#include <xnnpack/isa-checks.h>

#include <xnnpack/vcvt.h>
#include "vcvt-microkernel-tester.h"
""".format(specification=options.spec, generator=sys.argv[0])

    for ukernel_spec in spec_yaml:
      name = ukernel_spec["name"]
      init_fn = ukernel_spec.get("init")
      input_datatype, output_datatype, batch_tile, arch, isa = \
        split_ukernel_name(name)

      test_case = generate_test_cases(
        name, init_fn, input_datatype, output_datatype, batch_tile, isa)
      tests += "\n\n" + xnncommon.postprocess_test_case(test_case, arch, isa)

    txt_changed = True
    if os.path.exists(options.output):
      with codecs.open(options.output, "r", encoding="utf-8") as output_file:
        txt_changed = output_file.read() != tests

    if txt_changed:
      with codecs.open(options.output, "w", encoding="utf-8") as output_file:
        output_file.write(tests)


if __name__ == "__main__":
  main(sys.argv[1:])
