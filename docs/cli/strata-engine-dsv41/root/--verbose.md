# `--verbose`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DSv4.1 専用エンジン。ソースの usage 表記は `maya-ds4`） |
| オプション | `--verbose` |
| 別名 | `-v` |
| 値 | 取らないフラグ |

## 役割

エンジンの起動、モデル読み込み、expert 配置や prompt 処理などの診断情報を標準エラーへ追加します。通常の計算結果を変えるオプションとしては使われず、`Options::verbose` がログ出力条件に使われます。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --ids 1,2,3 --verbose
```

`--verbose` は引数解析中の任意の位置に置けます。モデル pack と実行モード（例では `--ids`）は別途必要です。`-v` も同じフラグです。

## 値と既定値

- 値は不要です。指定すると `o.verbose = true` となり、未指定時は `Options::verbose` の初期値 `false` のままです。
- `--verbose=true` のような値付き形式は定義されていません。未知オプションとして usage を表示して終了コード 2 になります。
- 複数回指定の個別エラー処理はありません。毎回 true を設定し、その都度 build 情報を stderr に出力します。
- parser に `--verbose` と `-v` が定義されています。usage の文字列には長形式だけが載っています。

## 実行時の動作

parser は `--verbose` または `-v` を受け取ると verbose フラグを有効にし、直ちに `ds4: build <build id> (<version>)` を stderr に出します。設定は `Options` としてモデル処理へ渡され、その後の複数箇所で追加情報の出力条件になります。例として、読み込み時間とモデル概要、GPU staging ring の見積り、CPU lane の thread/tier 情報、ロードや expert コピーの進捗、Windows commit 状況、prompt 経路の予測、expert cache の集計などを出力します。これらのログはモデル状態や実行経路に応じて現れるため、全ての実行で全項目が出るわけではありません。

verbose によりログが増えますが、確認した使用箇所では条件分岐はログ出力に限られ、計算値や選択経路を verbose の有無で切り替える処理は確認できません。なお `DS4_FLOW_STATS` 環境変数が設定されている場合、flow の統計ログは `--verbose` なしでも出力されます。

## 適用条件と副作用

DSv4.1 エンジンの引数 parser のオプションです。モデルの GPU、RAM、expert cache、vision、prompt 経路など、各診断ログに対応する処理が実行された場合にその情報が出ます。主な副作用は stderr への追加出力で、ファイルやネットワークへの書き込みはこのフラグの処理では行いません。

## 出力とエラー

- 指定時、build ID と Strata version を stderr に出力します。診断ログも `fprintf(stderr, ...)` で書かれます。
- このフラグ自体の値検証・失敗経路はありません。値を伴わないフラグなので、次の引数を消費しません。
- `--verbose=...` など未認識の形式は `unknown option ...` と usage を stderr に出し、終了コード 2 で終了します。通常の `--help` は usage を stderr に表示し終了コード 0 です。

## 根拠

- parser と alias、フラグ設定、指定時の build/version 出力: `src/dsv41/ds4_main.cpp:1248-1250`。
- usage の表示名とオプション一覧: `src/dsv41/ds4_main.cpp:85-93`。
- `Options::verbose` の既定値: `src/dsv41/ds4_model.hpp:60`。
- verbose 条件付きの読み込み・配置・進捗・CPU lane・vision・cache・prompt 経路ログ: `src/dsv41/ds4_model.cu:2376-2377,2488-2489,2532-2535,2648,2778,2811-2813,3876-3878,4037-4039,4120-4124,4138-4140,4178-4181,4273-4275,4390-4392,4657-4662,5203-5206,5944-5948,7642-7649,7742-7747`。
- `DS4_FLOW_STATS` による独立した出力条件: `src/dsv41/ds4_model.cu:8085-8092`。
- 未知オプションのエラー、usage、終了コード: `src/dsv41/ds4_main.cpp:1266-1272`。
- `Options` の実行時ログ出力への利用箇所を確認しました。リポジトリの全 platform/build 構成での診断文面や出力量は実行確認していません。
