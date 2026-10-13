# strata-envvars

Strata で使用可能な環境変数がリリースの度に増えてるようで追いきれない。

そこで、

1. リリースノート眺めて目に入った環境変数ひとつをピックアップして、何をどう使ってる環境変数なのか、どういう値を設定できるのか、どういう条件が満たされたら使われるのか、実行時にどう効いてるのか、、、といった私が知りたい事柄の要望を詰めて、会話ラリーして調査させてサンプルとして1本をコーディングエージェントに仕上げてもらう。
1. このサンプルと、サンプルを作り上げた過程をもとに、環境変数1個を渡されてから仕上げるまでの調査マニュアルを、コーディングエージェントに作ってもらう。
1. 環境変数の一覧をコーディングエージェントに作ってもらう。550個ありました。
1. 最後に、こんな感じでコーディングエージェントに1セッションで1個の環境変数を調査してもらう

```bash
seq $(wc -l $HOME/src/github.com/Niko1221/Strata-EnvVars/000_envvers.md) \
| xargs -P6 -L1 -I{} time codex exec --skip-git-repo-check --sandbox 'workspace-write' \
'調査依頼です。調査対象ソースコードは `$HOME/src/github.com/Niko1221/Strata` です。 `$HOME/src/github.com/Niko1221/Strata-EnvVars/000_envvers.md` から、 `$HOME/src/github.com/Niko1221/Strata-EnvVars/` に調査結果ファイルが存在しない環境変数を、任意に1個を選んで、 `$HOME/src/github.com/Niko1221/Strata-EnvVars/001_investigation.md` の指示に従って、 `$HOME/src/github.com/Niko1221/Strata-EnvVars/` に調査結果ファイルを作成してください。環境変数1個ずつ調べてください。'
```

私の手元では OpenAI Codex で GPT-6 Luna xhigh で、5時間制限 1.6 回くらいで完走しました。xargs の並列数の増減と、5時間制限の消費を見ながら、ペース配分はお好みで。

なお手元パソコンで Radeon R9700 1枚で OpenCode で Strata Qwen3.8 Flash Next IQ2_XXS reasonig_efort=high でやらせたら、1変数に5分から15分くらい要してました。このペースでは何日かかるかわからんぞ...と。いうことで、私は手元で使用枠の余ってた Codex でガッとやらせました。

# つまり何を設定したら prefill や decode が増えるのよ!!

知らん、わからん、頑張って読解してほしい。

# 最新版 Strata ソースコードに追従

どうやっていくか no plan だぜ。

# コマンドライン引数

環境変数もそうだけど、コマンドライン引数も興味がある。
