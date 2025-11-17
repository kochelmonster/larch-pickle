#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from benchmark import load_documents, measure, serializers, Item
import matplotlib.pyplot as plt

# Run the benchmark
documents = load_documents()

# Data types
data_types = [
    ("Dictionaries", documents),
    ("Objects", [Item(*args) for args in documents]),
    ("Strings", repr(documents).split("{") * 2),
    ("Lists", [[[d]] for d in repr(documents).split("{") * 2])
]

# Collect results
results = {}
for name, data in data_types:
    dump_table, load_table, loops = measure(data, 10)  # Use 10 loops
    results[name] = (dump_table, load_table)

# Plot function
def plot_times(data_types_results, title_suffix):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    
    for i, (data_type, (dump_table, load_table)) in enumerate(data_types_results.items()):
        ax = axes[i]
        
        # Dump times
        dump_labels = [row[0] for row in dump_table]
        dump_times = [row[1] for row in dump_table]
        
        ax.bar(range(len(dump_labels)), dump_times, color='blue', alpha=0.7, label='Dump Time')
        
        # Load times (overlay)
        load_labels = [row[0] for row in load_table]
        load_times = [row[1] for row in load_table]
        
        ax.bar(range(len(load_labels)), load_times, color='red', alpha=0.7, label='Load Time', bottom=dump_times)
        
        ax.set_xticks(range(len(dump_labels)))
        ax.set_xticklabels(dump_labels, rotation=45, ha='right')
        ax.set_ylabel('Time (seconds)')
        ax.set_title(f'{data_type} {title_suffix}')
        ax.legend()
    
    plt.tight_layout()
    plt.savefig('benchmark_graph.png', dpi=300)
    plt.show()

# Plot
plot_times(results, 'Serialization Benchmark')