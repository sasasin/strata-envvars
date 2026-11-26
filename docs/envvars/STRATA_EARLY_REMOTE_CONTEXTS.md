# `STRATA_EARLY_REMOTE_CONTEXTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata generate` が helper GPU の expert cache 用デバイスを初期化する順序を切り替える。既定では remote cache の最初のデバイス（`--expert-cache-device1`）だけを主 GPU の後続処理より前に preflight し、device2/3 は後段で初期化する。値の先頭が `1` の場合は、設定された remote cache の全デバイスを早期に preflight する。remote cache を有効化したり cache slot 数を変えたりはせず、順序だけを変える（CUDA/HIP: `engine/src/program/generate.cpp:5511-5525,8466-8476`; SYCL: `engine/sycl/src/program/generate.cpp:2811-2825,4613-4623`）。

## 値と判定

両実装とも `std::getenv` の戻り値が非 null で、最初の文字が `'1'` なら真とする。文字列全体の比較や数値変換はしない。したがって unset、空文字、`0`、`true`、先頭が空白の ` 1` は無効、`1`、`10`、`1anything` は有効。大文字小文字や後続文字は判定に関係せず、数値妥当性・範囲検査もない。既定値は false（CUDA/HIP: `engine/src/program/generate.cpp:5514-5516`; SYCL: `engine/sycl/src/program/generate.cpp:2814-2816`）。

| 実装 | unset（remote cache 指定時） | 早期化する値 | 早期化しない値 |
|---|---|---|---|
| CUDA/HIP engine | device1 相当のみ | 先頭文字が `1`（例: `1`, `10`, `1x`） | 空文字、`0`, `true`, ` 1` など |
| SYCL engine | device1 相当のみ | 先頭文字が `1`（例: `1`, `10`, `1x`） | 空文字、`0`, `true`, ` 1` など |

## 有効になる条件

- `--expert-cache-device1`、`--expert-cache-device2`、`--expert-cache-device3` のうち、対応する remote cache の slot 数が正であること。各 CLI 値は `auto` または `atoi` で整数化され、初期値は 0 のため、未指定や 0 以下ならその cache 用 preflight は行われない（CUDA/HIP: `engine/src/program/generate.cpp:904-905,3988-3993,5516`; SYCL: `engine/sycl/src/program/generate.cpp:576-577,2006-2010,2816`）。
- device1 相当（内部 index 0）はこの変数の値にかかわらず早期 preflight される。device2/3 相当（index 1/2）のみがこの変数の判定で早期化され、無効値または未設定なら後段に回る（CUDA/HIP: `engine/src/program/generate.cpp:5516,8468`; SYCL: `engine/sycl/src/program/generate.cpp:2816,4615`）。
- helper が実際に割り当てられる device は `--layer-split` の有無や primary device によって決まる。必要な remote cache がない GPU を要求した場合などは、この変数に関係なく既存の CLI 検証で拒否される（CUDA/HIP: `engine/src/program/generate.cpp:4882-4893,4954-4968`; SYCL: `engine/sycl/src/program/generate.cpp:2351-2357,2421-2438`）。
- 対象名を読む実装は CUDA/HIP engine と SYCL engine の `generate.cpp`。同じ early/late 分岐に OS や serve-mode 条件はなく、値を読むのはそれぞれの `generate` 起動経路である（上記読み取り行と preflight の位置を参照）。

## 実行時の詳細

環境値は `generate.cpp` の expert layout 検証後、preflight ループに入る時に読み、そのローカルな `early_remote` に保存する。関数内で一度だけ読むため、同じ実行中に環境値を変更しても再評価されない。子プロセスへの転送・上書き処理はこの読み取り経路にはない（CUDA/HIP: `engine/src/program/generate.cpp:5385-5411,5511-5516`; SYCL: `engine/sycl/src/program/generate.cpp:2784-2816`）。

有効なとき、正の slot 数がある各 remote cache について `RemoteExperts::preflight` を呼び、後続の主 GPU の重い処理より前に対象 device を選択し、使用可能性と空きメモリを確認する。無効または未設定なら index 1/2 の preflight を後段（CUDA/HIP は `engine/src/program/generate.cpp:8466-8476`、SYCL は `engine/sycl/src/program/generate.cpp:4613-4623`）まで延期する。CUDA/HIP preflight は CUDA runtime の初期化呼び出しと device scope を使い、HIP では `cudaInitDevice` 相当の呼び出しを行わない。SYCL preflight は device scope と memory info を使う（CUDA/HIP: `engine/src/core/remote_experts.cpp:71-97`; SYCL: `engine/sycl/src/core/remote_experts.cpp:90-123`）。

CLI 側の slot 数や他の環境変数との優先上書きはない。この設定は `--expert-cache-deviceN` が作る対象デバイス集合に対する初期化時期だけに作用する。CUDA/HIP preflight 内の `STRATA_REMOTE_SPIN` 判定は別の設定であり、この変数の値判定には使われない（`engine/src/core/remote_experts.cpp:83-91`）。

## ログと測定値

各 early/late preflight が成功すると stderr に `strata generate: CUDA%d context ready, %.2f GiB free before expert arena registration` を出す（CUDA/HIP: `engine/src/program/generate.cpp:5520-5525,8470-8475`; SYCL: `engine/sycl/src/program/generate.cpp:2820-2825,4617-4622`）。失敗時は preflight が設定したエラーを `strata generate: %s` として stderr に出し、その経路は終了コード 1 を返す。CUDA/HIP の例として device が見えない場合は `CUDA%d experts: CUDA device is not visible`、device 切替失敗時は `CUDA%d experts: cudaSetDevice(%d) failed: ... (CUDA error %d)` となる（`engine/src/core/remote_experts.cpp:71-80,92-97`; 呼び出し側 `engine/src/program/generate.cpp:5520-5523`）。SYCL preflight で `sycl::exception` が投げられた場合は例外情報とファイル・行を stderr に出して `std::exit(1)` する（`engine/sycl/src/core/remote_experts.cpp:125-129`）。この変数自体の速度測定値は記載しない。

## 根拠

- CUDA/HIP の読み取り、値判定、早期 preflight: `engine/src/program/generate.cpp:5511-5525`。
- CUDA/HIP の遅延 preflight: `engine/src/program/generate.cpp:8466-8476`。
- SYCL の読み取り、値判定、早期 preflight: `engine/sycl/src/program/generate.cpp:2811-2825`。
- SYCL の遅延 preflight: `engine/sycl/src/program/generate.cpp:4613-4623`。
- CLI slot の初期値と parser: `engine/src/program/generate.cpp:904-905,3988-3993`; `engine/sycl/src/program/generate.cpp:576-577,2006-2010`。
- Preflight の backend 処理: `engine/src/core/remote_experts.cpp:71-97`; `engine/sycl/src/core/remote_experts.cpp:90-129`。
