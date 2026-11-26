# `STRATA_REMOTE_ZEROCOPY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

helper GPU の remote expert 処理で、入力と計算結果の pinned host buffer を GPU が直接参照する zero-copy 経路を選ぶ。`0` で始まる値を指定するとこの経路を使わず、通常の host-to-device / device-to-host コピーを行う。対象コードは CUDA/HIP 共用実装と SYCL 実装の `RemoteExperts::open`、`begin` である。helper GPU の remote expert cache を使わない実行では読み取り箇所に到達せず、この変数は作用しない（`engine/src/core/remote_experts.cpp:136-139,233-238`; `engine/sycl/src/core/remote_experts.cpp:136-139,312-317`）。

## 値と判定

両実装とも `std::getenv` で文字列を読み、値全体の parse はせず、設定値の先頭文字が `'0'` かだけを見る。未設定、空文字、先頭が `0` でない値は候補として ON。文字列の大文字小文字、数値としての妥当性、後続文字は検査しない。

| 実装・追加条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP 共用実装。さらに CUDA では pinned buffer の device pointer 取得が両 buffer とも成功すること | zero-copy を試す | 空文字、`1`、`true`、` 0`、`false`、先頭が `0` でない文字列 | `0`、`0anything`。また CUDA でどちらかの `cudaHostGetDevicePointer` が失敗した場合 |
| SYCL 実装 | zero-copy を試す | 空文字、`1`、`true`、先頭が `0` でない任意の文字列 | `0`、`0anything` |

`0` の判定は `zc && zc[0] == '0'` なので、空文字は設定済みでも無効化せず、`0.5` や `0anything` は無効化する一方、` 0` や `false` は無効化しない。CUDA/HIP 共用実装では判定後に `cudaHostGetDevicePointer` の成否も必要で、失敗時は `zero_copy_` が false になりコピー経路に戻る。SYCL 実装では `z_x_` と `z_out_` に pinned host buffer のアドレスを設定し、変数が先頭 `0` でなければそのポインター経路を選ぶ（`engine/src/core/remote_experts.cpp:233-239`; `engine/sycl/src/core/remote_experts.cpp:312-317`）。

## 有効になる条件

- 起動引数で helper remote expert cache を 1 つ以上有効にし、`RemoteExperts::open` が呼ばれること。通常の CUDA0 単独実行や `--peer-device` だけの経路では、この環境変数を読むコードを通らない（`engine/src/program/generate.cpp:10123-10130,10197-10207`; `docs/SECOND_GPU.md:11-20,28-48,70-74`）。
- CUDA/HIP 共用実装では helper device に pinned host buffer を確保し、CUDA の場合は入力・出力両 buffer の device pointer 取得に成功すること。取得失敗は機能を無効にしてコピー経路へ戻る（`engine/src/core/remote_experts.cpp:211-239`）。
- SYCL では remote experts の SYCL 実装が使われること。そこで `STRATA_REMOTE_ZEROCOPY` 以外の環境変数や CLI フラグを使った追加の zero-copy 判定はない（`engine/sycl/src/core/remote_experts.cpp:312-317`）。
- `--remote-expert-opt` が有効な CUDA remote expert 処理では、zero-copy の入力側は引き続き使われる。CUDA の通常出力先は `reduce` 時に `d_out_` となり、結果集約は `RemoteExpertOpt::reduce` に進む。SYCL のこの箇所には同じ `reduce` 分岐がないため、出力条件は異なる（`engine/src/core/remote_experts.cpp:320-348`; `engine/src/core/remote_expert_opt.cu:100-112`; `engine/sycl/src/core/remote_experts.cpp:431-452`）。

## 実行時の詳細

値は `RemoteExperts::open` の初期化中に通常の局所変数として一度読み、`zero_copy_` に保存される。CUDA/HIP 共用実装では各 helper の `open` ごと、SYCL でも同様に初期化時に評価する。関数内 static cache やリクエストごとの再読込はないので、プロセス実行中に環境を変更しても既に開いた helper には反映されず、再初期化が必要となる（`engine/src/core/remote_experts.cpp:136-139,233-239`; `engine/sycl/src/core/remote_experts.cpp:312-317`）。

`begin` は入力を pinned host buffer にコピーした後、zero-copy が無効なら入力を device buffer に転送する。zero-copy が有効なら CUDA/HIP 共用実装は `z_x_`、SYCL は `z_x_` を量子化処理に渡す。計算結果は通常、zero-copy 無効時に device buffer から pinned host buffer にコピーされ、zero-copy 有効時はホスト側の出力 buffer を出力先に選ぶ。CUDA の `--remote-expert-opt` 有効時はその出力先選択に例外がある（`engine/src/core/remote_experts.cpp:311-354`; `engine/sycl/src/core/remote_experts.cpp:400-452`）。

CUDA で zero-copy を選べなかった場合、あるいは環境変数で無効化した場合に行う通常コピーの失敗は、`copy input` または `copy results` と CUDA エラー文字列を含む `err` になる。呼び出し側は `strata generate: <err>` を stderr に出して終了コード 1 を返す。zero-copy を使わないこと自体を知らせるログはなく、CUDA のポインター取得失敗後は `cudaGetLastError()` でエラー状態を読み捨てる。初期化成功時には helper のスロット数・GiB と「results return through pinned host rows」を stderr に出すが、このログは zero-copy の成否を示さない（`engine/src/core/remote_experts.cpp:235-239`; `engine/src/program/generate.cpp:10197-10207`）。SYCL の API エラーは `check` の `err` 経路のほか、捕捉された `sycl::exception` について例外文字列とファイル・行を stderr に出して `exit(1)` する（`engine/sycl/src/core/remote_experts.cpp:346-350,458-461`）。

## 根拠

- `engine/src/core/remote_experts.cpp:136-139,211-239,311-358` — helper 初期化時の環境値判定、CUDA/HIP 共用経路でのポインター取得、入力・出力コピーの分岐。
- `engine/sycl/src/core/remote_experts.cpp:136-139,312-317,400-452` — SYCL 実装の判定と入出力経路。
- `engine/src/program/generate.cpp:10123-10130,10197-10207` — helper cache 条件、初期化、失敗・起動ログ。
- `engine/src/core/remote_expert_opt.cu:100-112` — CUDA の remote expert 最適化における出力集約。
- `docs/SECOND_GPU.md:11-20,28-48,56-74` — remote helper の利用条件。
