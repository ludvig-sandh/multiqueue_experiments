add_library(threading STATIC util/threading.cpp)
target_include_directories(threading PUBLIC "${CMAKE_SOURCE_DIR}/util")
target_link_libraries(threading PUBLIC Threads::Threads)
target_compile_features(threading PUBLIC cxx_std_17)

add_library(benchmark_base INTERFACE)
target_include_directories(benchmark_base INTERFACE "." "..")
target_include_directories(benchmark_base SYSTEM
                           INTERFACE "${CMAKE_SOURCE_DIR}/third_party")
target_compile_definitions(benchmark_base
                           INTERFACE L1_CACHE_LINE_SIZE=${L1_CACHE_LINE_SIZE})
target_compile_definitions(benchmark_base INTERFACE PAGE_SIZE=${PAGE_SIZE})
target_compile_features(benchmark_base INTERFACE cxx_std_20)
target_link_libraries(benchmark_base INTERFACE threading)
if(PAPI_FOUND)
  target_link_libraries(benchmark_base INTERFACE PAPI::PAPI)
  target_compile_definitions(benchmark_base INTERFACE WITH_PAPI)
endif()

### PMC library
find_package(OpenMP REQUIRED)

add_library(pmc_core OBJECT
  ${CMAKE_SOURCE_DIR}/third_party/pmc-dimacs/pmc_utils.cpp
  ${CMAKE_SOURCE_DIR}/third_party/pmc-dimacs/pmc_graph.cpp
  ${CMAKE_SOURCE_DIR}/third_party/pmc-dimacs/pmc_clique_utils.cpp
  ${CMAKE_SOURCE_DIR}/third_party/pmc-dimacs/pmc_heu.cpp
  ${CMAKE_SOURCE_DIR}/third_party/pmc-dimacs/pmc_maxclique.cpp
  ${CMAKE_SOURCE_DIR}/third_party/pmc-dimacs/pmcx_maxclique.cpp
  ${CMAKE_SOURCE_DIR}/third_party/pmc-dimacs/pmcx_maxclique_basic.cpp
  ${CMAKE_SOURCE_DIR}/third_party/pmc-dimacs/pmc_cores.cpp
)

target_include_directories(pmc_core PUBLIC
  ${CMAKE_SOURCE_DIR}/third_party/pmc-dimacs
)

# GCC LTO fails to resolve PMC's internal cross-object references from the
# archive in clean builds, so keep this third-party integration out of IPO.
set_target_properties(pmc_core PROPERTIES INTERPROCEDURAL_OPTIMIZATION FALSE)
target_compile_features(pmc_core PUBLIC cxx_std_17)
target_link_libraries(pmc_core PUBLIC OpenMP::OpenMP_CXX)

add_library(pmc STATIC
  ${CMAKE_SOURCE_DIR}/third_party/pmc-dimacs/pmc_lib.cpp
  $<TARGET_OBJECTS:pmc_core>
)

target_include_directories(pmc PUBLIC
  ${CMAKE_SOURCE_DIR}/third_party/pmc-dimacs
)

set_target_properties(pmc PROPERTIES INTERPROCEDURAL_OPTIMIZATION FALSE)
target_compile_features(pmc PUBLIC cxx_std_17)
target_link_libraries(pmc PUBLIC OpenMP::OpenMP_CXX)
###

add_library(monotonic_base INTERFACE)
target_sources(monotonic_base INTERFACE monotonic.cpp)
target_link_libraries(monotonic_base INTERFACE benchmark_base)

add_library(push_pop_base INTERFACE)
target_sources(push_pop_base INTERFACE push_pop.cpp)
target_link_libraries(push_pop_base INTERFACE benchmark_base)

add_library(dijkstra_base INTERFACE)
target_sources(dijkstra_base INTERFACE dijkstra.cpp)
target_link_libraries(dijkstra_base INTERFACE benchmark_base)

add_library(old_knapsack_base INTERFACE)
target_sources(old_knapsack_base INTERFACE old_knapsack.cpp)
target_link_libraries(old_knapsack_base INTERFACE benchmark_base)

add_library(old_knapsack_float_base INTERFACE)
target_sources(old_knapsack_float_base INTERFACE old_knapsack.cpp)
target_link_libraries(old_knapsack_float_base INTERFACE benchmark_base)
target_compile_definitions(old_knapsack_float_base INTERFACE FLOAT_INSTANCE)

add_library(knapsack_base INTERFACE)
target_sources(knapsack_base INTERFACE knapsack.cpp)
target_link_libraries(knapsack_base INTERFACE benchmark_base)

add_library(mdkp_base INTERFACE)
target_sources(mdkp_base INTERFACE mdkp.cpp)
target_link_libraries(mdkp_base INTERFACE benchmark_base)

add_library(max_clique_base INTERFACE)
target_sources(max_clique_base INTERFACE max_clique.cpp)
target_link_libraries(max_clique_base INTERFACE benchmark_base)

if(EXP_TUNING_TARGETS)
  add_custom_target(tuning_all)
  add_custom_target(tuning_log_all)
endif()

foreach(benchmark monotonic push_pop dijkstra old_knapsack old_knapsack_float knapsack mdkp max_clique)
  add_custom_target(${benchmark}_all)
  add_custom_target(${benchmark}_log_all)
  if(EXP_TUNING_TARGETS)
    add_custom_target(${benchmark}_tuning_all)
    add_custom_target(${benchmark}_log_tuning_all)
  endif()
endforeach()

function(add_benchmark benchmark target)
  add_executable(${benchmark}_${target})
  target_link_libraries(${benchmark}_${target} PRIVATE ${target}
                                                       ${benchmark}_base)

  add_executable(${benchmark}_log_${target})
  target_link_libraries(${benchmark}_log_${target} PRIVATE ${target}
                                                           ${benchmark}_base)
  target_compile_definitions(${benchmark}_log_${target} PRIVATE LOG_OPERATIONS)
endfunction()

foreach(target ${COMPETITORS})
  foreach(benchmark monotonic push_pop dijkstra old_knapsack knapsack mdkp max_clique)
    add_benchmark(${benchmark} ${target})
    add_dependencies(${benchmark}_all ${benchmark}_${target})
    add_dependencies(${benchmark}_log_all ${benchmark}_log_${target})
  endforeach()
endforeach()

foreach(target ${GENERIC_COMPETITORS})
  add_benchmark(old_knapsack_float ${target})
  add_dependencies(old_knapsack_float_all old_knapsack_float_${target})
  add_dependencies(old_knapsack_float_log_all old_knapsack_float_log_${target})
endforeach()

if(EXP_TUNING_TARGETS)
  foreach(target ${TUNING_TARGETS})
    foreach(benchmark monotonic push_pop dijkstra knapsack knapsack_float)
      add_benchmark(${benchmark} ${target})
      add_dependencies(${benchmark}_tuning_all ${benchmark}_${target})
      add_dependencies(${benchmark}_log_tuning_all ${benchmark}_log_${target})
    endforeach()
  endforeach()
endif()

add_executable(dijkstra_seq dijkstra_seq.cpp)
target_link_libraries(dijkstra_seq PRIVATE benchmark_base)

add_executable(old_knapsack_seq old_knapsack_seq.cpp)
target_link_libraries(old_knapsack_seq PRIVATE benchmark_base)

add_executable(old_knapsack_float_seq old_knapsack_seq.cpp)
target_link_libraries(old_knapsack_float_seq PRIVATE benchmark_base)
target_compile_definitions(old_knapsack_float_seq PRIVATE FLOAT_INSTANCE)

add_executable(knapsack_seq_pq knapsack_seq_pq.cpp)
target_link_libraries(knapsack_seq_pq PRIVATE benchmark_base)

add_executable(max_clique_seq_pq max_clique_seq_pq.cpp)
target_link_libraries(max_clique_seq_pq PRIVATE benchmark_base)

add_executable(max_clique_seq_stack max_clique_seq_stack.cpp)
target_link_libraries(max_clique_seq_stack PRIVATE benchmark_base)

add_executable(max_clique_work_stealing max_clique_work_stealing.cpp)
target_link_libraries(max_clique_work_stealing PRIVATE benchmark_base)

add_executable(max_clique_pmc max_clique_pmc.cpp)
set_target_properties(max_clique_pmc PROPERTIES INTERPROCEDURAL_OPTIMIZATION FALSE)
target_link_libraries(max_clique_pmc PRIVATE pmc benchmark_base)

add_executable(knapsack_seq_stack knapsack_seq_stack.cpp)
target_link_libraries(knapsack_seq_stack PRIVATE benchmark_base)

add_executable(mdkp_seq_pq mdkp_seq_pq.cpp)
target_link_libraries(mdkp_seq_pq PRIVATE benchmark_base)
