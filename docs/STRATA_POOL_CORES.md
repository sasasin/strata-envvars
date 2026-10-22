# `STRATA_POOL_CORES`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU expert pool の worker を割り当てる論理プロセッサのリストを指定します。Strata の `generate` 実行ファイルが起動時に読み取り、CPU pool の構築前に解析して配置設定へ保存します。CUDA 版と SYCL 版の `generate` に同じ処理があります。既定の配置は変えず、空でない有効なリストを与えた場合だけ指定配置を使います。

## 値と判定

環境変数の値は整数へ変換せず、文字列全体を `parse_pool_cores()` に渡します。値は論理プロセッサ番号のカンマ区切り、昇順範囲、またはその組み合わせです。範囲の `:step` は省略時 `1` です。

| 値 | 動作 |
|---|---|
| 未設定 | `--pool-cores` も空なら、従来の既定配置を使う。 |
| 空文字 | `--pool-cores` も空なら何も設定せず、既定配置を使う。 |
| 有効な非空文字列 | 指定番号を順序どおりに保持して pool の候補 worker CPU に設定する。 |
| 不正な文字列 | stderr に `strata generate: --pool-cores: ...; the pool uses its default placement` を出し、既定配置を使う。 |

例: `0,2,4,6`、`2-14:2`、`0-3,8,10-14:2`。数値は ASCII の数字のみで、各数値は `0..100000`、各範囲は昇順、step は正数でなければなりません。前後や区切り周辺の ASCII space / tab は読み飛ばします。重複番号は最初の一つだけ残り、結果が 4096 個を超えるリストは拒否されます。負数、空要素、末尾カンマ、文字列の後置、逆順範囲、step 0 は不正です。大小文字の規則は該当しません。

CLI の `--pool-cores` が空でないときは環境変数より優先されます。CLI 値が空文字の場合は環境変数へフォールバックします。したがって、空の CLI 値で設定済み環境変数だけを無効化することはできません。不正な非空 CLI 値は環境変数にフォールバックせず、既定配置になります。

## 有効になる条件

- `src/program/generate.cpp` または `sycl/src/program/generate.cpp` の `generate` 起動経路で使われます。`strata-q36` は独自の worker 配置を使い、この設定の読み取り箇所はありません。
- CPU pool が構築される必要があります。`--pool-workers N` が指定されると worker 数は `N` で、リストの先頭から使います。`N` がリストより大きい場合、リストにない余分な worker は未 pin です。`N` が 0（自動）の場合、明示リストの利用可能な項目数が worker 数になります。
- Strata は OS が列挙した／プロセスが使用可能な論理プロセッサと照合します。存在しない番号やプロセスの affinity 制限外の番号は除外します。使える番号が一つも残らなければ既定配置になります。
- Windows は processor group と process affinity mask、Linux は現在の thread の affinity mask を使って照合します。macOS では hardware concurrency の番号を候補にしますが、OS による thread pinning がないため指定番号は実際の固定配置になりません。
- 同一物理 core の SMT sibling を複数指定した場合や、host thread と同じ CPU / core を指定した場合も項目は維持し、stderr に共有を知らせる警告を出します。配置要求を自動で別 CPU へ置き換えません。
- この設定は thread placement を変えます。Strata の資料は結果を変えないと説明していますが、特定の配置による性能向上は保証していません。

## 実行時の詳細

CLI 引数の解析後、CPU pool より前に `--pool-cores` の文字列を選びます。文字列が空なら `getenv("STRATA_POOL_CORES")` を調べ、非空なら parser を呼びます。成功時にプロセス内の pool 設定へ保存し、pool 構築時に現在の CPU topology と照合します。環境変数をリクエストごとに再評価する処理はなく、起動後の環境変更は反映されません。

有効な番号は指定順を維持し、pool worker の CPU として使われます。`--pool-workers` も指定されていない場合は、その有効番号数が worker 数の基準になります。使用不可番号は `strata cpu pool: --pool-cores: left out: ...` として通知されます。同じ core の sibling や host CPU の共有も `strata cpu pool: --pool-cores: ...` の警告対象です。全番号が使用不可なら `strata cpu pool: --pool-cores: no usable logical processor in the list; the pool uses its default placement` を出します。worker の pin 自体に失敗した場合は affinity 失敗を stderr に出し、以前の affinity を維持します。

サーバー設定の `pool_cores` も `serve/server.py` が `--pool-cores` 引数に変換します。CLI 引数に既に `--pool-cores` があればサーバー設定は追加されません。この変換は環境変数読み取りではなく、engine に渡す引数を作る処理です。

## 根拠

- 引数保存、help の値例と条件: `src/program/generate.cpp:523-524,1022-1028,2512`。SYCL 側: `sycl/src/program/generate.cpp:506-507,936-938,1843`。
- 環境変数との優先順位、起動時の解析、不正値ログ: `src/program/generate.cpp:2862-2872`。SYCL 側: `sycl/src/program/generate.cpp:2080-2090`。
- 数値、空白、区切り、重複、range、上限の parser: `include/strata/kernels/cpu/pool_plan.hpp:180-225`。
- 使用可能 CPU の照合、除外、SMT / host 共有警告: `include/strata/kernels/cpu/pool_plan.hpp:227-281`; Windows / Linux の CPU topology: `src/kernels/cpu/pool.cpp:91-137`。
- macOS の CPU 候補と pin no-op: `src/kernels/cpu/pool_affinity_linux.hpp:69-86`。
- pool での候補設定、worker 数、NUMA 並べ替えの扱い、警告と既定配置 fallback: `src/kernels/cpu/pool.cpp:763-779,785-817,840-849`。
- worker ごとの pin と pin 失敗ログ: `src/kernels/cpu/pool.cpp:580-591,923-935`; 起動時の pool 生成と配置ログ: `src/program/generate.cpp:5870-5908`。
- サーバー設定からの CLI 化と既存 CLI 優先: `serve/server.py:2994-2996,3023-3046`。
- 仕様の説明と測定の範囲: `docs/DETAILS.md:2123-2140`。この資料は指定配置の機能を説明しますが、個別の `STRATA_POOL_CORES` 配置に対する性能差の測定値は示していません。
