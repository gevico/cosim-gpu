# SPDX-License-Identifier: Apache-2.0

# libvfio-user v0.8 PCI headers use C's _Static_assert in C++.
function(cosim_rocjitsu_vfio_gcc_compat)
    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND TARGET rocjitsu_vmm_vfu)
        target_compile_definitions(rocjitsu_vmm_vfu PRIVATE
            _Static_assert=static_assert)
    endif()
endfunction()

cmake_language(DEFER CALL cosim_rocjitsu_vfio_gcc_compat)
