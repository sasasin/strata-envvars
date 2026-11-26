# `IGC_EnableDPEmulation`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata のエンジン本体がこの環境変数を読んで処理を切り替える箇所はありません。Strata が行うのは、Intel SYCL セットアップが条件に合う GPU の実行設定へ `IGC_EnableDPEmulation=1` を書くこと、および設定された環境変数をサーバーと SYCL 起動ラッパーが子プロセス・コンテナへ渡すことです。セットアップは同じ設定ブロックに `OverrideDefaultFP64Settings=1` と `NEOReadDebugKeys=1` も書きます（`engine/sycl/setup_intel.py:414-431`）。

Intel の資料は Arc A-series 用の設定として3つのキーを挙げていますが、ここでは Strata 側の設定・転送だけを記録します。GPU driver 側でこの値がどう解釈されるか、および実際にどのカーネル動作が変わるかは Strata の環境変数読み取りではないため対象外です（`docs/INTEL.md:252-264`）。

## 値と判定

エンジン本体での値判定はありません。SYCL セットアップの自動設定と、`strata launch --set` の汎用環境設定では次のとおりです。

| 経路 | unset | 値の扱い | 空文字・無効値 |
|---|---|---|---|
| `engine/sycl/setup_intel.py` の自動設定 | 対象 GPU 以外ではこのキーを自動設定しない | 対象 GPU では文字列 `1` を設定する | 値を parse せず、他の値を検査するコードもない（`engine/sycl/setup_intel.py:389-390,414-431`） |
| `strata launch --set IGC_EnableDPEmulation=...` | 指定しなければ既存の設定環境をこの引数では変更しない | `=` の後の文字列を trim し、`off`・`unset`・`none`（大文字小文字を区別しない）以外はそのまま設定値にする | `--set IGC_EnableDPEmulation` または `=`, `=   ` は空文字を設定ブロックに入れる。`off`・`unset`・`none` は設定ブロックからキーを削除する。`0`、`true`、`false`、`0anything` などをこの処理は真偽値に変換しない（`terminal/strata_cli/launch/settings.py:365-377,380-385,392-417`; `terminal/strata_control/tune_knobs.py:536-543`） |

`--set` のキー名は大文字を少なくとも1文字含む環境変数形式に一致する必要があり、この名前は大文字小文字を保って受理されます。キーと値の前後空白を除き、最初の `=` で分割します。繰り返し指定したキーは辞書への後の代入で置き換わります（`terminal/strata_cli/launch/settings.py:361-385`）。この対象名を受理する例はテストにもあります（`terminal/tests/terminal/test_launch.py:71-80`）。

## 有効になる条件

- 自動設定は Intel SYCL セットアップが選んだカードについて、ドライバーが `i915` または PCI device ID が Alchemist の ID 集合（`56a0`, `56a1`, `56a2`, `56a5`, `56a6`, `5690`）に該当するときに行われます。条件式は `driver == "i915" or devid in ALCHEMIST_IDS` です（`engine/sycl/setup_intel.py:48-58,389-390`）。
- このセットアップは `/sys/class/drm` から Intel の `xe` / `i915` デバイスを列挙し、Windows では Intel デバイス一覧を空にします。列挙できる Intel Arc がなければセットアップは失敗します（`engine/sycl/setup_intel.py:95-119,436-444`）。
- `strata launch --set` は値をエンジン設定の `env` に反映する汎用経路です。対象キーは専用の許可リストや GPU 判定を通りません（`terminal/strata_cli/launch/cmd.py:124-125,302-303`; `terminal/strata_cli/launch/runner.py:801-806`）。
- 環境ブロックに同じキーがあれば、`--set KEY=value` の値がその設定を上書きします。`--set KEY=off|unset|none` は設定ブロックのキーを削除しますが、サーバーはまず自身の環境を子環境の基礎にするため、サーバー起動時から同名変数が設定されていればその値は残ります。設定ブロックの値は継承値より後に適用されます（`terminal/strata_cli/launch/runner.py:802-806`; `terminal/serve/server.py:4007-4028`）。
- SYCL ラッパーは `IGC_` で始まる変数をコンテナ設定へ取り込み、空文字は渡さず、それ以外は値をそのまま渡します。したがって `--set IGC_EnableDPEmulation=` の空文字はホスト側の子環境には設定されますが、このラッパーではコンテナへ渡されません。値 `0` は空文字でないため転送対象です（`engine/sycl/serve/strata-sycl.sh:13-16,33-43`）。

## 実行時の詳細

この名前に対する Strata の直接読み取りやキャッシュはありません。自動設定は Intel セットアップが `to_sycl()` で実行設定を組み立てる時に行われ、設定 JSON へ書き出されます（`engine/sycl/setup_intel.py:322-324,414-431,526-538,577-579`）。`strata launch` では `--set` を引数から解析して設定ブロックへ適用します（`terminal/strata_cli/launch/cmd.py:124-125,302-303`; `terminal/strata_cli/launch/runner.py:801-806`）。

SYCL エンジン起動時、サーバーは親プロセス環境を複製した後に設定 JSON の `env` の各項目を適用します。SYCL ラッパーは `IGC_` 変数をコンテナ起動引数へ加えます（`terminal/serve/server.py:4007-4028`; `engine/sycl/serve/strata-sycl.sh:33-51`）。サーバー起動後に親プロセスの環境を変更しても、その変更はすでに作られた子プロセス環境には反映されません。設定ファイルや起動引数の変更も、再起動して設定が再適用されるまで反映されません。

## ログと測定値

この変数の読み取り・値検査に伴う Strata の専用ログ、警告、終了・失敗経路は見つかりませんでした。Intel セットアップは該当条件で設定値を書き込みますが、このキーに関する通知は出しません（`engine/sycl/setup_intel.py:414-431,577-579`）。値を転送した後の GPU driver や SYCL runtime の結果は Strata のコードから確認できないため、記載できる Strata 側の測定値はありません。

## 根拠

- `engine/sycl/setup_intel.py:48-58,95-119,322-342,389-431,436-444,526-538,567-579` — Intel GPU の判定、自動設定条件、環境ブロックの生成・保存。
- `terminal/strata_cli/launch/settings.py:361-417`, `terminal/strata_cli/launch/cmd.py:124-125,302-303`, `terminal/strata_cli/launch/runner.py:801-806`, `terminal/strata_control/tune_knobs.py:536-543` — `--set` のキー・値解析と環境設定の適用。
- `terminal/serve/server.py:4007-4028,9386-9394` — 親環境からの子環境生成と設定環境の優先適用。
- `engine/sycl/serve/strata-sycl.sh:13-16,33-51` — `IGC_` 変数の転送と空文字の除外。
- `docs/INTEL.md:252-264`, `terminal/tests/terminal/test_launch.py:71-80`, `engine/sycl/probe/fp64_cost.cpp:1-4`, `engine/sycl/tools/test_prompt_deadlock.sh:11`, `engine/sycl/src/kernels/router_top10_parity.cpp:130` — 資料・テスト・コメント上の候補参照。これらはドライバー側の効果を Strata の読み取りとして裏付けるものではありません。
