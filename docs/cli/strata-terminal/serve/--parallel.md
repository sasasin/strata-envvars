# `strata serve --parallel`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--parallel` |
| 別名 | なし |
| 値 | 整数 `N`。CLI では `1..1024` |

## 役割

既存の serving profile に対し、この起動時だけ同時推論 slot 数を要求します。`strata serve` は既存 API と engine を foreground で起動し、profile は事前に用意しておく必要があります。このオプションは profile を書き換えません。

## 使い方

```sh
strata serve --profile /path/to/run.json --parallel 4
```

`--profile`（または alias `--config`）も必須です。例の `4` は値の指定例であり、推奨値や性能保証ではありません。

## 値と既定値

- `argparse` が整数として読み取り、未指定時の CLI 値は `None` です。明示値は `1..1024` に制限され、範囲外は起動前に拒否されます。
- 明示しない場合は保存済み profile override、次に run config の `parallel` 値を使います。どちらにも値がなければ `parallel` は設定されず、通常は単一 request 処理になります。ただし run config の `args` に `--batch` / `--slots` があれば、その engine 引数が別途有効です。
- engine の設定値としては整数が必要です。1 以下または未設定なら `--batch` は追加されません。2 以上なら server が engine 引数へ `--batch N` を追加します。
- `1..1024` は Terminal CLI の入力範囲で、engine が実際に確保・実行する slot 数の保証ではありません。

## 実行時の動作

優先順位はコマンドライン指定、保存済み profile の override、run config の値、未設定の順です。CLI 値は effective config に反映され、server 起動引数を通じて server に渡されます。run config の `args` に `--batch` または `--slots` がすでにある状態で CLI または saved profile の `parallel` override を適用すると競合エラーになります。run config 自身の `parallel` 値と同じ config の engine 引数指定は共存し、明示された engine 引数が優先されます。

Strata engine では `parallel >= 2` が `--batch N` となり、最大 N 件の request が batch slot で同時に decode できるよう要求します。先行する request が処理中でも後続 request が slot を使える一方、要求数が engine の対応範囲や利用可能な GPU memory を超えると engine が値を縮小するか batch を無効にすることがあります。server は engine が報告した実 slot 数と要求値が異なる場合、起動ログに差を表示します。telemetry の `slots_requested` と `slots_effective` も照合できます。

## 適用条件と副作用

- `--engine strata`（既定）では、各 slot が独立した session state を持つため GPU memory を使います。engine は slot session が収まらない場合に slot 数を減らし、2 slot 未満しか収まらない場合は batch を無効にします。
- 通常の batch window は最大 8 row です。8 を超える要求は MTP などの条件がなければ engine が window に収まる数へ縮めます。engine 固有条件により要求値が拒否・補正されることもあります。
- `--engine mock` は GPU・model を使わない scripted engine 用です。この場合、Strata engine の batch slot 挙動は適用されません。
- server の queue 上限や待ち時間はこのオプションでは設定しません。別オプション `--max-queue` / `--queue-timeout` が担当します。

## 出力とエラー

- 整数でない引数は parser が usage とエラーを表示して終了コード 2 で終了します。
- `1..1024` の範囲外は server 起動前に拒否されます。通常出力では `strata: --parallel must be in 1..1024` を stderr に出し、終了コード 2 を返します。`--output json` では JSON error、`--output jsonl` では `failed` event を stdout に出します。
- run config 内の `--batch` / `--slots` と CLI override が競合する場合も、起動前の validation で拒否されます。
- 要求値が engine で使えない場合、server または engine が stdout/stderr に診断を出し、実際の batch slot 数を下げるか batch を無効にします。無効・縮小の具体的理由は engine の起動ログを確認してください。

## 根拠

- parser と必須 config、型: `strata_cli/cli.py:46-54`
- CLI と profile / run config の優先順位、validation、args 競合: `strata_cli/cli.py:745-779`
- server 引数への転送と effective config: `strata_cli/cli.py:794-824`
- 範囲検証とエラー処理: `strata_cli/cli.py:915-939`、`strata_cli/cli.py:527-542,829-835`
- profile override の整数・範囲 validation: `strata_control/profiles.py:66-107`
- server 側の `--parallel` parser、重複する競合検査と config への反映: `serve/server.py:8161-8164,8269-8275`
- engine `--batch` への変換、1 以下・無効型・8 超の扱い: `serve/server.py:3127-3153`
- engine が使った slot 数と要求値の差の通知: `serve/server.py:1134-1140`
- 通常の window 上限、batch の無効化・GPU memory による縮小: `src/program/generate.cpp:910-912,5341-5355,5386-5440`
- profile 未指定時の `parallel` 値と telemetry の requested slots: `serve/server.py:8450-8460`
- Terminal CLI の `serve` 概要・設定を変更しない旨: `docs/TERMINAL.md:220-222`
- batch slot の利用者向け説明: `docs/BATCHING.md:1-10,159-162`
