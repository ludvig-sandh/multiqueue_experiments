set_directory_properties(PROPERTIES EXCLUDE_FROM_ALL TRUE)

find_package(GSL)

add_library(mq INTERFACE)
target_link_libraries(mq INTERFACE multiqueue::multiqueue)
target_compile_definitions(mq INTERFACE PQ_MQ)

add_library(mq_random INTERFACE)
target_compile_definitions(mq_random INTERFACE MQ_MODE_RANDOM)
target_link_libraries(mq_random INTERFACE mq)

add_library(mq_random_strict INTERFACE)
target_compile_definitions(mq_random_strict INTERFACE MQ_MODE_RANDOM_STRICT)
target_link_libraries(mq_random_strict INTERFACE mq)

add_library(mq_stick_random INTERFACE)
target_compile_definitions(mq_stick_random INTERFACE MQ_MODE_STICK_RANDOM)
target_link_libraries(mq_stick_random INTERFACE mq)

add_library(mq_stick_swap INTERFACE)
target_compile_definitions(mq_stick_swap INTERFACE MQ_MODE_STICK_SWAP)
target_link_libraries(mq_stick_swap INTERFACE mq)

add_library(mq_stick_mark INTERFACE)
target_compile_definitions(mq_stick_mark INTERFACE MQ_MODE_STICK_MARK)
target_link_libraries(mq_stick_mark INTERFACE mq)

add_library(mq_stick_parametric INTERFACE)
target_compile_definitions(mq_stick_parametric
                           INTERFACE MQ_MODE_STICK_PARAMETRIC)
target_link_libraries(mq_stick_parametric INTERFACE mq)

list(APPEND MQ_VARIANTS mq_random mq_random_strict mq_stick_random
     mq_stick_swap mq_stick_mark)

if(EXP_TUNING_TARGETS)
  foreach(i ${EXP_TUNING_POP_PQS})
    add_library(mq_tuning_pop_${i} INTERFACE)
    target_link_libraries(mq_tuning_pop_${i} INTERFACE mq)
    target_compile_definitions(
      mq_tuning_pop_${i}
      INTERFACE MQ_MODE_RANDOM MQ_INSERTION_BUFFER_SIZE=0
                MQ_DELETION_BUFFER_SIZE=0 MQ_HEAP_ARITY=2 MQ_NUM_POP_PQS=${i})
    list(APPEND TUNING_TARGETS mq_tuning_pop_${i})
  endforeach()
  foreach(ibs ${EXP_TUNING_BUFFER_SIZES})
    foreach(dbs ${EXP_TUNING_BUFFER_SIZES})
      foreach(d ${EXP_TUNING_HEAP_ARITIES})
        add_library(mq_tuning_ibs_${ibs}_dbs_${dbs}_d_${d} INTERFACE)
        target_link_libraries(mq_tuning_ibs_${ibs}_dbs_${dbs}_d_${d}
                              INTERFACE mq)
        target_compile_definitions(
          mq_tuning_ibs_${ibs}_dbs_${dbs}_d_${d}
          INTERFACE MQ_MODE_RANDOM MQ_INSERTION_BUFFER_SIZE=${ibs}
                    MQ_DELETION_BUFFER_SIZE=${dbs} MQ_HEAP_ARITY=${d}
                    MQ_NUM_POP_PQS=2)
        list(APPEND TUNING_TARGETS mq_tuning_ibs_${ibs}_dbs_${dbs}_d_${d})
      endforeach()
      add_library(mq_tuning_ibs_${ibs}_dbs_${dbs}_std INTERFACE)
      target_link_libraries(mq_tuning_ibs_${ibs}_dbs_${dbs}_std INTERFACE mq)
      target_compile_definitions(
        mq_tuning_ibs_${ibs}_dbs_${dbs}_std
        INTERFACE MQ_MODE_RANDOM MQ_INSERTION_BUFFER_SIZE=${ibs}
                  MQ_DELETION_BUFFER_SIZE=${dbs} MQ_HEAP_ARITY=2
                  MQ_NUM_POP_PQS=2 MQ_USE_STD_PQ)
      list(APPEND TUNING_TARGETS mq_tuning_ibs_${ibs}_dbs_${dbs}_std)
    endforeach()
  endforeach()
  add_library(mq_tuning_btree INTERFACE)
  target_link_libraries(mq_tuning_btree INTERFACE mq)
  target_compile_definitions(
    mq_tuning_btree
    INTERFACE MQ_USE_BTREE MQ_MODE_RANDOM MQ_NUM_POP_PQS=2)
  list(APPEND TUNING_TARGETS mq_tuning_btree)

  set(TUNING_TARGETS
      ${TUNING_TARGETS}
      PARENT_SCOPE)
endif()

set(KLSM_DIR "${CMAKE_SOURCE_DIR}/third_party/klsm")

add_library(klsm ${KLSM_DIR}/src/util/thread_local_ptr.cpp)
target_include_directories(klsm SYSTEM INTERFACE ${KLSM_DIR}/src
                                                 ${KLSM_DIR}/src/util)
add_library(klsm4 INTERFACE)
target_link_libraries(klsm4 INTERFACE klsm)
set_property(TARGET klsm4 PROPERTY pq_name klsm4)
target_compile_definitions(
  klsm4
  INTERFACE PQ_KLSM
  INTERFACE KLSM_K=4)
add_library(klsm256 INTERFACE)
target_link_libraries(klsm256 INTERFACE klsm)
set_property(TARGET klsm256 PROPERTY pq_name klsm256)
target_compile_definitions(
  klsm256
  INTERFACE PQ_KLSM
  INTERFACE KLSM_K=256)
add_library(klsm1024 INTERFACE)
target_link_libraries(klsm1024 INTERFACE klsm)
set_property(TARGET klsm1024 PROPERTY pq_name klsm1024)
target_compile_definitions(
  klsm1024
  INTERFACE PQ_KLSM
  INTERFACE KLSM_K=1024)
add_library(klsm4096 INTERFACE)
target_link_libraries(klsm4096 INTERFACE klsm)
set_property(TARGET klsm4096 PROPERTY pq_name klsm4096)
target_compile_definitions(
  klsm4096
  INTERFACE PQ_KLSM
  INTERFACE KLSM_K=4096)

add_library(smq INTERFACE)
set_property(TARGET smq PROPERTY pq_name smq)
target_compile_definitions(smq INTERFACE PQ_SMQ)

add_library(
  linden
  ${KLSM_DIR}/lib/spraylist_linden/linden_common.c
  ${KLSM_DIR}/lib/spraylist_linden/linden.c
  ${KLSM_DIR}/lib/spraylist_linden/gc/gc.c
  ${KLSM_DIR}/lib/spraylist_linden/gc/ptst.c)
target_compile_options(linden PRIVATE -w -std=gnu++17)
target_compile_definitions(linden PUBLIC INTEL
                                         CACHE_LINE_SIZE=${L1_CACHE_LINE_SIZE} _GNU_SOURCE)
target_include_directories(
  linden SYSTEM
  PUBLIC ${KLSM_DIR}/lib ${KLSM_DIR}/lib/spraylist_linden/atomic_ops
         ${KLSM_DIR}/lib/spraylist_linden/include)
set_property(TARGET linden PROPERTY pq_name linden)
target_compile_definitions(linden INTERFACE PQ_LINDEN)
target_link_libraries(linden PUBLIC GSL::gsl)

add_library(
  capq STATIC
  ${KLSM_DIR}/lib/capq/capq.c
  ${KLSM_DIR}/lib/capq/fat_skiplist.c
  ${KLSM_DIR}/lib/capq/qdlocksrc/locks/qd_lock.c
  ${KLSM_DIR}/lib/capq/qdlocksrc/locks/tatas_lock.c
  ${KLSM_DIR}/lib/capq/gc/gc.c
  ${KLSM_DIR}/lib/capq/gc/ptst.c)
target_include_directories(
  capq SYSTEM PUBLIC ${KLSM_DIR}/lib ${KLSM_DIR}/lib/capq
                     ${KLSM_DIR}/lib/capq/qdlocksrc)
target_compile_options(capq PRIVATE -w -std=gnu11)
target_compile_definitions(capq PUBLIC INTEL
                                        CACHE_LINE_SIZE=${L1_CACHE_LINE_SIZE})
target_compile_definitions(capq INTERFACE PQ_CAPQ)
target_link_libraries(capq PUBLIC GSL::gsl)

add_library(
  spraylist
  ${KLSM_DIR}/lib/spraylist_linden/fraser.c
  ${KLSM_DIR}/lib/spraylist_linden/intset.c
  ${KLSM_DIR}/lib/spraylist_linden/linden_common.c
  ${KLSM_DIR}/lib/spraylist_linden/linden.c
  ${KLSM_DIR}/lib/spraylist_linden/measurements.c
  ${KLSM_DIR}/lib/spraylist_linden/pqueue.c
  ${KLSM_DIR}/lib/spraylist_linden/skiplist.c
  ${KLSM_DIR}/lib/spraylist_linden/ssalloc.c)
target_compile_options(spraylist PRIVATE -w -std=gnu17)
target_compile_definitions(
  spraylist PUBLIC INTEL LOCKFREE _GNU_SOURCE CACHE_LINE_SIZE=${L1_CACHE_LINE_SIZE})
target_include_directories(
  spraylist SYSTEM
  PUBLIC ${KLSM_DIR}/lib ${KLSM_DIR}/lib/spraylist_linden/atomic_ops
         ${KLSM_DIR}/lib/spraylist_linden/include)
set_property(TARGET spraylist PROPERTY pq_name spraylist)
target_compile_definitions(spraylist INTERFACE PQ_SPRAYLIST)
target_link_libraries(spraylist PUBLIC GSL::gsl)

find_package(TBB)

if(TBB_FOUND)
  add_library(tbb_pq INTERFACE)
  target_link_libraries(tbb_pq INTERFACE tbb)
  target_compile_definitions(tbb_pq INTERFACE PQ_TBB_PQ)
else()
  message(WARNING "TBB not found, not building TBB priority queue")
endif()

add_library(locked_pq INTERFACE)
target_compile_definitions(locked_pq INTERFACE PQ_LOCKED_PQ)

add_library(locked_stack INTERFACE)
target_compile_definitions(locked_stack INTERFACE PQ_LOCKED_STACK)

add_library(mq_pq INTERFACE)
target_link_libraries(mq_pq INTERFACE multiqueue::multiqueue)
target_compile_definitions(mq_pq INTERFACE PQ_MQ_PQ)

add_library(multilifo_support STATIC
            ${CMAKE_SOURCE_DIR}/third_party/multififo/relaxed_concurrent_fifo/contenders/multififo/timestamp.cpp)
target_include_directories(
  multilifo_support PUBLIC ${CMAKE_SOURCE_DIR}/third_party
                           ${CMAKE_SOURCE_DIR}/third_party/multififo/relaxed_concurrent_fifo/contenders/multififo)

add_library(multilifo INTERFACE)
set_property(TARGET multilifo PROPERTY pq_name multilifo)
target_link_libraries(multilifo INTERFACE multilifo_support)
target_compile_definitions(multilifo INTERFACE PQ_MULTILIFO)

set(PR_DIR "${CMAKE_SOURCE_DIR}/third_party/PR-bench-impl")

add_library(
  pr_support STATIC
  ${PR_DIR}/common.c
  ${PR_DIR}/prioq.c
  ${PR_DIR}/gc/gc.c
  ${PR_DIR}/gc/ptst.c)
target_include_directories(pr_support SYSTEM PUBLIC ${PR_DIR} ${PR_DIR}/gc)
target_compile_options(pr_support PRIVATE -w -std=gnu11)
target_compile_definitions(pr_support PUBLIC INTEL _GNU_SOURCE
                                             CACHE_LINE_SIZE=${L1_CACHE_LINE_SIZE})

add_library(pr INTERFACE)
set_property(TARGET pr PROPERTY pq_name pr)
target_link_libraries(pr INTERFACE pr_support)
target_compile_definitions(pr INTERFACE PQ_PR)

set(TWO_D_STACK_DIR "${CMAKE_SOURCE_DIR}/third_party/2d-stacks")

add_library(
  2d_stack_support STATIC
  ${TWO_D_STACK_DIR}/2Dc-stack.c
  ${TWO_D_STACK_DIR}/ssmem.c
  ${TWO_D_STACK_DIR}/ssalloc.c)
target_include_directories(2d_stack_support SYSTEM PUBLIC ${TWO_D_STACK_DIR})
target_compile_options(2d_stack_support PRIVATE -w -std=gnu11 -mcx16)
target_compile_definitions(2d_stack_support PUBLIC GC=1 GCCLAIM=0
                                                   CORES_PER_SOCKET=1 NO_SET_CPU)
target_link_libraries(2d_stack_support PUBLIC atomic m)

add_library(2d_stack INTERFACE)
set_property(TARGET 2d_stack PROPERTY pq_name 2d_stack)
target_link_libraries(2d_stack INTERFACE 2d_stack_support)
target_compile_definitions(2d_stack INTERFACE PQ_2D_STACK)

set(LIBCDS_DIR "${CMAKE_SOURCE_DIR}/third_party/libcds")

add_library(
  libcds_support STATIC
  ${LIBCDS_DIR}/src/init.cpp
  ${LIBCDS_DIR}/src/hp.cpp
  ${LIBCDS_DIR}/src/hp_thread_local.cpp
  ${LIBCDS_DIR}/src/dhp.cpp
  ${LIBCDS_DIR}/src/urcu_gp.cpp
  ${LIBCDS_DIR}/src/urcu_sh.cpp
  ${LIBCDS_DIR}/src/thread_data.cpp
  ${LIBCDS_DIR}/src/topology_hpux.cpp
  ${LIBCDS_DIR}/src/topology_linux.cpp
  ${LIBCDS_DIR}/src/topology_osx.cpp
  ${LIBCDS_DIR}/src/dllmain.cpp)
target_include_directories(libcds_support SYSTEM PUBLIC ${LIBCDS_DIR})
target_compile_options(libcds_support PRIVATE -w)
target_compile_options(libcds_support PUBLIC -mcx16)
target_link_libraries(libcds_support PUBLIC Threads::Threads atomic)

add_library(treiber_stack INTERFACE)
set_property(TARGET treiber_stack PROPERTY pq_name treiber_stack)
target_link_libraries(treiber_stack INTERFACE libcds_support)
target_compile_definitions(treiber_stack INTERFACE PQ_TREIBER_STACK)

set(COMPETITORS
    ${MQ_VARIANTS}
    klsm4
    klsm256
    klsm1024
    klsm4096
    smq
    linden
    capq
    spraylist
    tbb_pq
    locked_pq
    locked_stack
    mq_pq
    multilifo
    pr
    2d_stack
    treiber_stack
    PARENT_SCOPE)

set(GENERIC_COMPETITORS
    ${MQ_VARIANTS}
    klsm4
    klsm256
    klsm1024
    klsm4096
    smq
    tbb_pq
    locked_pq
    locked_stack
    mq_pq
    multilifo
    pr
    2d_stack
    treiber_stack
    PARENT_SCOPE)
