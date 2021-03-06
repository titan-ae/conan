from conans.model import Generator
from conans.paths import BUILD_INFO_CMAKE


class DepsCppCmake(object):
    def __init__(self, deps_cpp_info):
        self.include_paths = "\n\t\t\t".join('"%s"' % p.replace("\\", "/")
                                             for p in deps_cpp_info.include_paths)
        self.lib_paths = "\n\t\t\t".join('"%s"' % p.replace("\\", "/")
                                         for p in deps_cpp_info.lib_paths)
        self.libs = " ".join(deps_cpp_info.libs)
        self.defines = "\n\t\t\t".join("-D%s" % d for d in deps_cpp_info.defines)
        self.cppflags = " ".join(deps_cpp_info.cppflags)
        self.cflags = " ".join(deps_cpp_info.cflags)
        self.sharedlinkflags = " ".join(deps_cpp_info.sharedlinkflags)
        self.exelinkflags = " ".join(deps_cpp_info.exelinkflags)
        self.bin_paths = "\n\t\t\t".join('"%s"' % p.replace("\\", "/")
                                         for p in deps_cpp_info.bin_paths)

        self.rootpath = '"%s"' % deps_cpp_info.rootpath.replace("\\", "/")


class CMakeGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO_CMAKE

    @property
    def content(self):
        sections = []

        # DEPS VARIABLES
        template_dep = ('set(CONAN_{dep}_ROOT {deps.rootpath})\n'
                        'set(CONAN_INCLUDE_DIRS_{dep} {deps.include_paths})\n'
                        'set(CONAN_LIB_DIRS_{dep} {deps.lib_paths})\n'
                        'set(CONAN_BIN_DIRS_{dep} {deps.bin_paths})\n'
                        'set(CONAN_LIBS_{dep} {deps.libs})\n'
                        'set(CONAN_DEFINES_{dep} {deps.defines})\n'
                        'set(CONAN_CXX_FLAGS_{dep} "{deps.cppflags}")\n'
                        'set(CONAN_SHARED_LINKER_FLAGS_{dep} "{deps.sharedlinkflags}")\n'
                        'set(CONAN_EXE_LINKER_FLAGS_{dep} "{deps.exelinkflags}")\n'
                        'set(CONAN_C_FLAGS_{dep} "{deps.cflags}")\n')

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            deps = DepsCppCmake(dep_cpp_info)
            dep_flags = template_dep.format(dep=dep_name.upper(),
                                            deps=deps)
            sections.append(dep_flags)

        # GENERAL VARIABLES
        deps = DepsCppCmake(self.deps_build_info)

        template = ('set(CONAN_INCLUDE_DIRS {deps.include_paths} ${{CONAN_INCLUDE_DIRS}})\n'
            'set(CONAN_LIB_DIRS {deps.lib_paths} ${{CONAN_LIB_DIRS}})\n'
            'set(CONAN_BIN_DIRS {deps.bin_paths} ${{CONAN_BIN_DIRS}})\n'
            'set(CONAN_LIBS {deps.libs} ${{CONAN_LIBS}})\n'
            'set(CONAN_DEFINES {deps.defines} ${{CONAN_DEFINES}})\n'
            'set(CONAN_CXX_FLAGS "{deps.cppflags} ${{CONAN_CXX_FLAGS}}")\n'
            'set(CONAN_SHARED_LINKER_FLAGS "{deps.sharedlinkflags} ${{CONAN_SHARED_LINKER_FLAGS}}")\n'
            'set(CONAN_EXE_LINKER_FLAGS "{deps.exelinkflags} ${{CONAN_EXE_LINKER_FLAGS}}")\n'
            'set(CONAN_C_FLAGS "{deps.cflags} ${{CONAN_C_FLAGS}}")\n'
            'set(CONAN_CMAKE_MODULE_PATH {module_paths} ${{CONAN_CMAKE_MODULE_PATH}})')

        rootpaths = [DepsCppCmake(dep_cpp_info).rootpath for _, dep_cpp_info
                     in self.deps_build_info.dependencies]
        module_paths = " ".join(rootpaths)
        all_flags = template.format(deps=deps, module_paths=module_paths)
        sections.append(all_flags)

        # MACROS
        sections.append(self._aux_cmake_test_setup())

        return "\n".join(sections)

    def _aux_cmake_test_setup(self):
        return """macro(CONAN_BASIC_SETUP)
    conan_check_compiler()
    conan_output_dirs_setup()
    conan_flags_setup()
    # CMake can find findXXX.cmake files in the root of packages
    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_MODULE_PATH})
endmacro()

macro(CONAN_FLAGS_SETUP)
    include_directories(SYSTEM ${CONAN_INCLUDE_DIRS})
    link_directories(${CONAN_LIB_DIRS})
    add_definitions(${CONAN_DEFINES})

    # For find_library
    set(CMAKE_INCLUDE_PATH ${CONAN_INCLUDE_DIRS} ${CMAKE_INCLUDE_PATH})
    set(CMAKE_LIBRARY_PATH ${CONAN_LIB_DIRS} ${CMAKE_LIBRARY_PATH})

    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${CONAN_CXX_FLAGS}")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${CONAN_C_FLAGS}")
    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${CONAN_SHARED_LINKER_FLAGS}")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${CONAN_EXE_LINKER_FLAGS}")

    if(APPLE)
        # https://cmake.org/Wiki/CMake_RPATH_handling
        # CONAN GUIDE: All generated libraries should have the id and dependencies to other
        # dylibs without path, just the name, EX:
        # libMyLib1.dylib:
        #     libMyLib1.dylib (compatibility version 0.0.0, current version 0.0.0)
        #     libMyLib0.dylib (compatibility version 0.0.0, current version 0.0.0)
        #     /usr/lib/libc++.1.dylib (compatibility version 1.0.0, current version 120.0.0)
        #     /usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1197.1.1)
        set(CMAKE_SKIP_RPATH 1)  # AVOID RPATH FOR *.dylib, ALL LIBS BETWEEN THEM AND THE EXE
                                 # SHOULD BE ON THE LINKER RESOLVER PATH (./ IS ONE OF THEM)
    endif()
    if(CONAN_LINK_RUNTIME)
        string(REPLACE "/MD" ${CONAN_LINK_RUNTIME} CMAKE_CXX_FLAGS_RELEASE ${CMAKE_CXX_FLAGS_RELEASE})
        string(REPLACE "/MDd" ${CONAN_LINK_RUNTIME} CMAKE_CXX_FLAGS_DEBUG ${CMAKE_CXX_FLAGS_DEBUG})
        string(REPLACE "/MD" ${CONAN_LINK_RUNTIME} CMAKE_C_FLAGS_RELEASE ${CMAKE_C_FLAGS_RELEASE})
        string(REPLACE "/MDd" ${CONAN_LINK_RUNTIME} CMAKE_C_FLAGS_DEBUG ${CMAKE_C_FLAGS_DEBUG})
    endif()
endmacro()

macro(CONAN_OUTPUT_DIRS_SETUP)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})

    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/lib)
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
endmacro()

macro(CONAN_SPLIT_VERSION VERSION_STRING MAJOR MINOR)
    #make a list from the version string
    string(REPLACE "." ";" VERSION_LIST ${${VERSION_STRING}})

    #write output values
    list(GET VERSION_LIST 0 ${MAJOR})
    list(GET VERSION_LIST 1 ${MINOR})
endmacro()

macro(ERROR_COMPILER_VERSION)
    message(FATAL_ERROR "Incorrect '${CONAN_COMPILER}' version 'compiler.version=${CONAN_COMPILER_VERSION}'"
                        " is not the one detected by CMake: '${CMAKE_CXX_COMPILER_ID}="${VERSION_MAJOR}.${VERSION_MINOR}')
endmacro()

macro(CHECK_COMPILER_VERSION)

    CONAN_SPLIT_VERSION(CMAKE_CXX_COMPILER_VERSION VERSION_MAJOR VERSION_MINOR)

    if("${CMAKE_CXX_COMPILER_ID}" STREQUAL "MSVC")
        # https://cmake.org/cmake/help/v3.2/variable/MSVC_VERSION.html
        if( (${CONAN_COMPILER_VERSION} STREQUAL "14" AND NOT ${VERSION_MAJOR} STREQUAL "19") OR
            (${CONAN_COMPILER_VERSION} STREQUAL "12" AND NOT ${VERSION_MAJOR} STREQUAL "18") OR
            (${CONAN_COMPILER_VERSION} STREQUAL "11" AND NOT ${VERSION_MAJOR} STREQUAL "17") OR
            (${CONAN_COMPILER_VERSION} STREQUAL "10" AND NOT ${VERSION_MAJOR} STREQUAL "16") OR
            (${CONAN_COMPILER_VERSION} STREQUAL "9" AND NOT ${VERSION_MAJOR} STREQUAL "15") OR
            (${CONAN_COMPILER_VERSION} STREQUAL "8" AND NOT ${VERSION_MAJOR} STREQUAL "14") OR
            (${CONAN_COMPILER_VERSION} STREQUAL "7" AND NOT ${VERSION_MAJOR} STREQUAL "13") OR
            (${CONAN_COMPILER_VERSION} STREQUAL "6" AND NOT ${VERSION_MAJOR} STREQUAL "12") )
            ERROR_COMPILER_VERSION()
        endif()
    elseif("${CONAN_COMPILER}" STREQUAL "gcc" OR "${CONAN_COMPILER}" MATCHES "Clang")
        if(NOT ${VERSION_MAJOR}.${VERSION_MINOR} VERSION_EQUAL "${CONAN_COMPILER_VERSION}")
           ERROR_COMPILER_VERSION()
        endif()
    else()
        message("Skipping version checking of not detected compiler...")
    endif()
endmacro()

macro(CONAN_CHECK_COMPILER)
    if( ("${CONAN_COMPILER}" STREQUAL "Visual Studio" AND NOT "${CMAKE_CXX_COMPILER_ID}" STREQUAL "MSVC") OR
        ("${CONAN_COMPILER}" STREQUAL "gcc" AND NOT "${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU") OR
        ("${CONAN_COMPILER}" STREQUAL "apple-clang" AND (NOT APPLE OR NOT ${CMAKE_CXX_COMPILER_ID} MATCHES "Clang")) OR
        ("${CONAN_COMPILER}" STREQUAL "clang" AND NOT ${CMAKE_CXX_COMPILER_ID} MATCHES "Clang") )
        message(FATAL_ERROR "Incorrect '${CONAN_COMPILER}', is not the one detected by CMake: '${CMAKE_CXX_COMPILER_ID}'")
    endif()
    CHECK_COMPILER_VERSION()
endmacro()
"""
