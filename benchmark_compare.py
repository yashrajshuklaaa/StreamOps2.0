import asyncio
import sys
import time
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.panel import Panel

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

console = Console(safe_box=True)

# Simulated times in seconds
LLM_THINKING_TIME = 8.0
INTENT_DETECTION_TIME = 1.5
K8S_COLD_START_TIME = 6.0
CODE_EXECUTION_TIME = 0.5

async def simulate_traditional():
    """Simulates a standard reactive architecture without Stream-Ops."""
    start = time.time()
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        
        # 1. LLM Generation
        task1 = progress.add_task("[yellow]LLM Chain-of-Thought Generation...", total=LLM_THINKING_TIME)
        elapsed = 0
        while elapsed < LLM_THINKING_TIME:
            await asyncio.sleep(0.05)
            elapsed += 0.2
            progress.update(task1, advance=0.2)
                
        # 2. Kubernetes Cold Start
        task2 = progress.add_task("[red]K8s Reactive Cold Start (Pulling Image)...", total=K8S_COLD_START_TIME)
        elapsed = 0
        while elapsed < K8S_COLD_START_TIME:
            await asyncio.sleep(0.05)
            elapsed += 0.2
            progress.update(task2, advance=0.2)
                
        # 3. Tool Execution
        task3 = progress.add_task("[blue]Executing Python Code...", total=CODE_EXECUTION_TIME)
        elapsed = 0
        while elapsed < CODE_EXECUTION_TIME:
            await asyncio.sleep(0.05)
            elapsed += 0.2
            progress.update(task3, advance=0.2)

    return time.time() - start

async def simulate_streamops():
    """Simulates the proactive Stream-Ops architecture."""
    start = time.time()
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        
        task1 = progress.add_task("[yellow]LLM Chain-of-Thought Generation...", total=LLM_THINKING_TIME)
        task2 = progress.add_task("[green]Stream-Ops Background Pre-warming...", total=K8S_COLD_START_TIME, visible=False)
        
        # Parallel Execution Simulation
        elapsed = 0
        while elapsed < LLM_THINKING_TIME:
            await asyncio.sleep(0.05)
            elapsed += 0.2
            
            # Update LLM Task
            progress.update(task1, advance=0.2)
            
            # Trigger Stream-Ops after intent detection window
            if elapsed >= INTENT_DETECTION_TIME:
                if not progress.tasks[task2].visible:
                    progress.update(task2, visible=True)
                progress.update(task2, advance=0.2)
                
        # By the time LLM finishes, K8s is already done! (Masked Latency)
        progress.update(task2, completed=K8S_COLD_START_TIME)
        
        # 3. Tool Execution (Instantly available)
        task3 = progress.add_task("[blue]Executing Python Code...", total=CODE_EXECUTION_TIME)
        elapsed = 0
        while elapsed < CODE_EXECUTION_TIME:
            await asyncio.sleep(0.05)
            elapsed += 0.2
            progress.update(task3, advance=0.2)

    return time.time() - start

async def main():
    console.print(Panel.fit("[bold magenta]Capstone Benchmark: Traditional vs Stream-Ops[/bold magenta]"))
    
    console.print("\n[bold]Scenario A: Traditional Reactive Autoscaling (Without Stream-Ops)[/bold]")
    trad_time = await simulate_traditional()
    
    console.print("\n[bold]Scenario B: Proactive Semantic Autoscaling (WITH Stream-Ops)[/bold]")
    stream_time = await simulate_streamops()
    
    console.print("\n[bold cyan]Benchmark Results[/bold cyan]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Architecture", style="dim", width=20)
    table.add_column("Time-to-First-Tool-Execution", justify="right")
    table.add_column("Latency Masked", justify="right")
    
    time_saved = trad_time - stream_time
    percentage = (time_saved / trad_time) * 100
    
    table.add_row(
        "Traditional", 
        f"[red]{trad_time:.2f}s[/red]", 
        "0.00s"
    )
    table.add_row(
        "Stream-Ops", 
        f"[green]{stream_time:.2f}s[/green]", 
        f"[bold green]{time_saved:.2f}s ({percentage:.1f}% faster)[/bold green]"
    )
    
    console.print(table)

if __name__ == "__main__":
    asyncio.run(main())
