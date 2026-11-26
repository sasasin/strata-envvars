# `STRATA_PREFILL_HELPER_SOURCE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata serve` の prompt prefill が、別 GPU の remote expert helper が VRAM cache に保持している expert blob を、その cache から host staging buffer へコピーして使う opt-in スイッチです。未設定または 0 判定では prefill の source は元の `srcp` のままです。有効時も変わるのは blob の取得元だけで、helper にない blob は従来の source に渡され、prefill の判断や計算は変更されません（`engine/src/program/generate.cpp:12315-12330`、`engine/include/strata/core/remote_experts.hpp:107-115`）。

この読み取りは `strata serve` の初期化中に一度だけ行われます。通常の `generate` 経路ではこの判定ブロックに入りません。`strata` 実行ファイルは CUDA/HIP GPU engine の CMake 定義にあり、SYCL は別プロジェクト、Metal は別 engine です（`engine/src/program/generate.cpp:12302-12330`、`engine/cmake/strata_gpu_engine.cmake:548-551`、`engine/CMakeLists.txt:3-7,20-32`）。

## 値と判定

`std::getenv` で設定有無を確認し、設定されていれば `std::atoi(hv) != 0` を条件にします。全体の文字列比較や変換エラー検査はありません。`atoi` は先頭の空白と符号を許し、先頭の 10 進整数部分だけを読み、数字以降の文字列を検査しません。数字で始まらない文字列と空文字は 0 になります（`engine/src/program/generate.cpp:12325-12326`）。

| 環境値 | 判定 | 例 |
|---|---|---|
| 未設定 | 無効 | 既定では helper source を使わない |
| 空文字、先頭が数値でない | 無効 | `""`, `true`, `false` |
| 先頭の整数部分が 0 | 無効 | `0`, `+0`, `-0`, `0anything`, `0x1` |
| 先頭の整数部分が 0 以外 | 有効候補 | `1`, `-1`, `2`, `1anything`, `  +1tail` |

`atoi` の戻り値が 0 以外でも、有効条件を満たさなければ helper source は作成されません。`int` に表せない数値文字列について、コードはエラー検査や fallback 値を定めていません（`engine/src/program/generate.cpp:12325-12327`）。

## 有効になる条件

- サーバーモードであること。通常の `generate` にはこの環境変数を使う判定がありません（`engine/src/program/generate.cpp:12302-12327`）。
- `srcp != nullptr` であること（同 `12325-12327`）。
- `multi_gpu` が false で `stages` が空、つまり layer split の複数 GPU prompt path ではないこと（同 `12325-12327`）。
- `o.batch <= 0` であること。batch slot を使う設定では helper source に切り替えません（同 `12325-12327`）。
- `prefill_helpers` が空でないこと。これは `drive.d.remote[]` に登録された remote expert cache が少なくとも一つあることを要します（同 `12320-12327,10242-10244`）。remote expert cache の起動には `--expert-cache-device1` といった設定に加えて `--expert-profile`、CUDA0 の `--expert-cache`、expert pool が必要です（`engine/src/program/generate.cpp:10127-10132`）。
- helper cache に対象の `(layer, expert)` があること。起動時に helper source が作られても個々の cache miss は元の source から取得します（`engine/include/strata/core/remote_experts.hpp:121-124,152-155`、`engine/src/core/remote_experts.cpp:457-493`）。

この環境変数を読むほかの環境変数、CLI 引数、設定ファイルによる値の上書きはありません。CLI は値の既定を上書きしませんが、`--expert-cache-device1..3` などで作られる helper cache の有無や上記 mode 条件には影響します。

## 実行時の詳細

サーバー初期化時、環境値が非ゼロで条件を満たすと `RemotePrefillSource` を作り、`prefill_src` を元の `srcp` から wrapper に切り替えます。`Prefill::init` にはこの `prefill_src` が渡されます（`engine/src/program/generate.cpp:12320-12330,13032-13040`）。環境値の判定結果自体は起動時に一度だけ決まり、実行中に環境を書き換えても wrapper の有効・無効は切り替わりません。

wrapper は blob ごとの問い合わせ時に helper の現在の cache 保持状態を調べます。保持されていれば helper の CUDA stream から blob を host buffer へ device-to-host コピーして stream を同期し、hit として返します。読み出し対象は helper cache の blob bytes です。保持されていない blob は元の source に渡され、helper の cache 状態を wrapper 内に固定保存しません（`engine/include/strata/core/remote_experts.hpp:56-63,107-115,121-124`、`engine/src/core/remote_experts.cpp:394-424,447-493`）。

複数 blob の copy では helper ごとにまとめて読み出し、helper hit 以外を一括で元の source に渡します。helper cache の読み出しで失敗した場合、コピー完了が確認できた hit は使い、残りは元の source へ回します。失敗理由の stderr 警告はプロセス内で最初の一度だけ出します。元の source の `copy_blobs` も失敗すると prefill stager はエラーを stderr に出して `std::abort()` します（`engine/src/core/remote_experts.cpp:408-423,464-500`、`engine/src/prefill/prefill.cpp:1233-1247`）。

## ログと測定値

条件を満たして wrapper を作成したとき、stderr に次の行を出します。

```text
strata serve: the prompt path reads the experts a helper cache holds from that cache (STRATA_PREFILL_HELPER_SOURCE)
```

各 server request の終了時には wrapper がその request で helper cache から得た blob 数と MiB を出します。helper read error 時は以下の警告が一度だけ出ます（`engine/src/program/generate.cpp:12329-12330,23949-23955`、`engine/src/core/remote_experts.cpp:496-500`）。

```text
strata serve: prefill helper source: N blobs / M.M MiB taken from a helper's cache in this request
prefill: a helper cache read failed (...); the file source fills that blob instead
```

`docs/DETAILS.md` には expert cache や helper cache に関する説明はありますが、この環境変数固有の動作や性能測定値は確認できませんでした。ここではソースから確認できる挙動のみ記載し、速度や出力への性能影響は断定しません。

## 根拠

- `engine/src/program/generate.cpp:12302-12330` — serve 条件、変数の読み取り、値判定、source の切替、初期ログ。
- `engine/src/program/generate.cpp:10127-10132,10242-10244,13032-13040,23949-23955` — helper cache の起動条件・登録、prefill への渡し方、request 単位のログ。
- `engine/include/strata/core/remote_experts.hpp:56-63,107-159` — helper cache コピー API と wrapper の source 動作。
- `engine/src/core/remote_experts.cpp:136-145,394-424,426-500` — remote cache の初期化、device-to-host copy、fallback、警告。
- `engine/src/prefill/prefill.cpp:1233-1247` — copy failure 時の prefill 側エラーと abort。
- `engine/cmake/strata_gpu_engine.cmake:548-551`、`engine/CMakeLists.txt:3-7,20-32` — GPU engine の対象と SYCL の分離。
