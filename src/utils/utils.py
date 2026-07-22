import matplotlib.pyplot as plt


def load_config():
    pass


def seconds_to_time_string(seconds):
    if seconds < 60:
        return f'{int(seconds)}s'
    elif seconds < 3600:
        minutes = seconds / 60
        return f'{int(minutes)}m'
    else:
        hours = seconds / 3600
        return f'{int(hours)}h'
    
def draw(symbol, timestamps, ticks, save_path):
    # Plot the data
    fig, ax = plt.subplots(1, 1)
    ax.plot(timestamps, ticks, marker='o')
    ax.set_xlabel('Time')
    ax.set_ylabel('Values')
    ax.set_title(f'{symbol} Values over Time')
    ax.grid(True)
    ax.tick_params(axis='x', rotation=45)  # Rotate x-axis labels for better readability

    # Display the plot
    fig.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)