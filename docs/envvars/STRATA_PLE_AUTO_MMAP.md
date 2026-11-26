# `STRATA_PLE_AUTO_MMAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`strata generate` が PLE（Per-Layer Embedding）テーブルを既定の direct I/O で開いたあと、起動時の読み込みプローブが遅い場合に `--ple-io mmap` へ自動で切り替えるかを制御する。`engine/src/program/generate.cpp` と `engine/sycl/src/program/generate.cpp` に同じ判定があるため、CUDA/HIP 系と SYCL 系の generate 実装が対象となる。Strata の読み取りはこの 2 箇所で、設定値を他プロセスへ転送する処理はない。

## 値と判定

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP 系、SYCL 系 | 自動切替しない（遅いと警告して direct を維持） | `std::atoi` の結果が非 0。例: `1`、`2`、`-1`、`1tail`、`1.5`、` 1` | `std::atoi` の結果が 0。例: 空文字、`0`、`0anything`、`true`、`false` |

判定は文字列全体の検証ではなく `std::atoi` であり、10 進整数として読み取れる先頭部分を使う。先頭空白と符号は許容され、数値の後ろの文字は無視される。数字で始まらない文字列・空文字は 0 になる。値の範囲検査や clamp はない。`atoi` で表現できない大きさの値については、このコードに独自の処理がない。明示的な `--ple-io` が指定されている場合は、環境変数が非 0 でも切り替えない（後述）。根拠: `engine/src/program/generate.cpp:818-819,3901,6362-6364`、`engine/sycl/src/program/generate.cpp:502-503,1940,3385-3387`。

## 有効になる条件

- PLE テーブルを開く経路であること。両実装とも `o.ple_gguf` が空でない場合にテーブルを開き、空ならこの読み込みとプローブは行わない（`engine/src/program/generate.cpp:6269,5213-5215`、`engine/sycl/src/program/generate.cpp:3350,2627-2629`）。
- 初期モードが `direct` であること。`--ple-io` の既定値は `direct`。`--ple-io mmap` または `ram` を指定した場合は初期モードが direct でないため、プローブも環境変数の読み取りもない（`engine/src/program/generate.cpp:818,6270-6272,6352`、`engine/sycl/src/program/generate.cpp:502,3351-3353,3375`）。
- `STRATA_PLE_PROBE` が未設定であること。設定値が空文字でも「設定あり」と判定され、プローブ全体が抑止される。その場合、この環境変数も評価されない（`engine/src/program/generate.cpp:6352`、`engine/sycl/src/program/generate.cpp:3375`）。
- プローブ値が `0` より大きく `15000` rows/s 未満であること。`15000` ちょうど以上では「fine」ログを出し、切替しない。0 以下では切替せず、遅い旨の警告も出さない（`engine/src/program/generate.cpp:6353-6357`、`engine/sycl/src/program/generate.cpp:3376-3380`）。プローブ関数はテーブルが 4096 行未満なら測定不能を返し、読み取り失敗時も非正値を返す（`engine/src/program/generate.cpp:3450-3471`、`engine/sycl/src/program/generate.cpp:1778-1796`）。
- `--ple-io` が明示されていないこと。コマンドラインまたは設定ファイルの args で `--ple-io direct` を渡しても `ple_io_explicit` が true になり、自動切替しない。値が有効でプローブが遅ければ警告を出し direct を保つ（`engine/src/program/generate.cpp:3901,6362-6364,6376-6381`、`engine/sycl/src/program/generate.cpp:1940,3385-3387,3399-3404`）。
- CUDA/HIP 系では、先行する `STRATA_PLE_AUTO_RAM` の residency policy が RAM モードを選ぶと、この変数の対象である direct モードではなくなるため mmap プローブに進まない。policy は `--ple-io` 未指定時にのみ検討され、ホストメモリ量などの admission 判定もある（`engine/src/program/generate.cpp:6303-6307,6316-6327,6352`）。この先行 policy は SYCL 実装には見つからない。

## 実行時の詳細

`--ple-io` の既定値は `direct` で、指定された場合は引数解析時に explicit フラグを立てる。PLE テーブルを開いた後、direct モードかつ `STRATA_PLE_PROBE` 未設定なら、同じ batched reader を使うランダム読み出しで rows/s を測る。テーブルが 4096 行以上なら最大 64 バッチを試し、経過時間が約 0.6 秒を超えたところで終了する。1 バッチは 4 token 分（64 rows）である（`engine/src/program/generate.cpp:3901,3446-3471,6352-6354`、SYCL: `engine/sycl/src/program/generate.cpp:1940,1774-1796,3375-3377`）。

遅い測定値に対して、明示指定なし、かつこの変数の `atoi` 結果が非 0 なら、Strata は警告分岐の代わりに direct テーブルを閉じ、`pio.mode` を `Mmap` に変え、`keepalive_ms` を 0 にして同じテーブルを再度開く。これはテーブルを `ram` として lock する指定ではない。再オープンに失敗すると `strata generate: <エラー内容>` を stderr に出して終了コード 1 を返し、direct へ戻す処理はない（`engine/src/program/generate.cpp:6364-6375`、`engine/sycl/src/program/generate.cpp:3387-3398`）。

環境変数はこの generate 起動時の分岐で読み取られ、static cache やリクエストごとの再読込はない。読み取り後の環境変更がその判定に反映される経路はない。子プロセスへの転送もこのコードにはない。

## ログと測定値

- プローブが 15000 rows/s 以上なら `strata generate: PLE direct read probe: %.0f rows/s (fine)` を stderr に出す（`engine/src/program/generate.cpp:6355-6356`、SYCL: `engine/sycl/src/program/generate.cpp:3378-3379`）。
- 遅く、環境変数が有効で、explicit な `--ple-io` がない場合は `strata generate: --ple-io direct measures slow here (...): using --ple-io mmap instead ...` を stderr に出して切り替える（`engine/src/program/generate.cpp:6364-6368`、SYCL: `engine/sycl/src/program/generate.cpp:3387-3391`）。
- 遅いが切替しない場合は `strata generate: WARNING: --ple-io direct measures slow here (...)` の警告を stderr に出す。環境変数未設定・atoi が 0・explicit な `--ple-io direct` がこの経路に該当する（`engine/src/program/generate.cpp:6376-6381`、SYCL: `engine/sycl/src/program/generate.cpp:3399-3404`）。

`docs/DETAILS.md:1215` も、direct の起動プローブは通常自動切替せず、`STRATA_PLE_AUTO_MMAP=1` で mmap へ切り替えると説明している。上記のソースでは `1` に限らず `atoi` 結果が非 0 の値が条件を満たす。また、明示的な `--ple-io direct` は切替を抑止する。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:1766`。
- CUDA/HIP 系 generate の既定値・CLI 解析・プローブ・再オープン: `engine/src/program/generate.cpp:818-819,3901,6350-6384`。
- CUDA/HIP 系プローブ測定: `engine/src/program/generate.cpp:3446-3472`。
- CUDA/HIP 系で先に実行される RAM policy: `engine/src/program/generate.cpp:6303-6349`。
- SYCL generate の既定値・CLI 解析・プローブ・再オープン: `engine/sycl/src/program/generate.cpp:502-503,1940,3373-3407`。
- SYCL プローブ測定: `engine/sycl/src/program/generate.cpp:1774-1797`。
- Strata の説明資料: `docs/DETAILS.md:1215`。
