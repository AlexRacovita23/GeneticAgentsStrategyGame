# GeneticAgentsStrategyGame

git clone https://github.com/AlexRacovita23/GeneticAgentsStrategyGame.git

Explanations for commands that are needed to train the AI Agents, start the game against an AI agent, or play local 1vs1 can be found in their corresponding files. As a quick start the following python scripts can be run for the default experience

Run the game in the local 1vs1 mode
python play_vs_human.py

Train the agents with the default configuration
python .\train_genetic.py

Play against best_final.json agent. The player needs to move the json to .\trained_genomes manually from the timestamped directory
python .\play_vs_ai.py

Play against a specific agent
python play_vs_ai.py --genome .\trained_genomes\'timestamp'\best_final.json

 The "--small-map" parameter can be passed in order to play on a smaller, faster match map

NOTE! The training script must be run before playing against an AI agent and 'timestamp' needs to be modified with the actual folder path for the trained agent
