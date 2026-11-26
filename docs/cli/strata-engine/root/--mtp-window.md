# `--mtp-window`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--mtp-window` |
| 別名 | なし |
| 値 | 64 bit 整数。正の値がモデルの最大 context セル数未満の場合に限り、そのセル数を attention 窓にする |

## 役割

MTP draft layer が注意を向ける過去セル数を指定します。既定値は 32768 セルです。値は MTP drafter の読み込みへ渡され、attention の対象範囲と drafter 用 K/V 状態のリング容量に反映されます。これは生成対象モデル本体の context 長を設定する引数ではありません。

## 使い方

```sh
# MTP runtime を使い、draft layer の過去セル窓を 8192 にする
strata --pack model.gguf --tokens 1,2 --mtp /path/to/mtp-runtime --spec 4 --mtp-window 8192
```

`--pack`、`--tokens`、`--mtp` には実際のモデル、入力 token、MTP runtime のパスを指定してください。

## 値と既定値

- 値は `std::atoll` で整数化されます。parser に数値の範囲検証や変換エラー検査はありません。オプションの値が欠けている場合は `--mtp-window needs a value` を stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3842-3846,4055-4057`）。
- 省略時は `32768` です（`engine/src/program/generate.cpp:1036-1038`、SYCL parser も `engine/sycl/src/program/generate.cpp:683-685`）。
- loader は `0 < 値 < 最大 context セル数` の場合だけその値を採用します。0、負数、最大 context セル数以上は拒否エラーにはならず、内部値 0（全セルを対象）にします（`engine/src/core/mtp.cpp:511-517,543-547`、SYCL は `engine/sycl/src/core/mtp.cpp:483-486`）。
- 同じ引数を複数回指定すると parser の反復中に同じ変数へ再代入されるため、最後の指定値が残ります（`engine/src/program/generate.cpp:3842-3843,4055-4057`）。

## 実行時の動作

CUDA/HIP と SYCL の parser は値を `Options::mtp_window` に格納し、MTP drafter の `load` に渡します。drafter は有効な正値なら `window_` に設定し、attention 用のセル ID をその幅で構成します。0 に正規化された場合は窓による絞り込みを行わず、全セルを対象にします（`engine/src/program/generate.cpp:4055-4057,8262-8265`、`engine/src/core/mtp.cpp:543-547,1342-1349`、`engine/sycl/src/program/generate.cpp:2049-2051,4539-4542`、`engine/sycl/src/core/mtp.cpp:483-486,1052-1059`）。

窓が正値で有効な場合、CUDA/HIP loader は drafter 用 K/V を `window + 4 * max_t + 64` セルのリングとして確保しようとします。リング用 pinned RAM が足りず状態初期化に失敗した場合は警告を stderr に出し、全体を VRAM に置く状態へフォールバックします（`engine/src/core/mtp.cpp:511-535`）。SYCL loader でも同じ値を `window_` と attention 容量の計算に使います（`engine/sycl/src/core/mtp.cpp:455-485`）。

通常の単体 MTP drafter と batch MTP の各 slot drafter の両方に同じ値が渡されます（CUDA/HIP: `engine/src/program/generate.cpp:8262-8265,8351-8367`、SYCL: `engine/sycl/src/program/generate.cpp:4539-4547`）。CUDA/HIP の会話設定 fingerprint にも MTP runtime が指定されている場合の値として記録されます（未指定時は `-1`、`engine/src/program/generate.cpp:14000-14011`）。

## 適用条件と副作用

- 実際に MTP runtime を読み込むには `--mtp` と `--spec` が必要です。`--mtp` を指定していても `--spec` が 2 未満なら `--mtp` は無視され、runtime はクリアされます。その経路では `--mtp-window` も drafter に適用されません（`engine/src/program/generate.cpp:8243-8248`、SYCL は `engine/sycl/src/program/generate.cpp:4525-4530`）。
- Metal build の `MtpDrafter::load` は `window` 引数を明示的に未使用として扱い、`mtp_load` に渡しません。この build では `--mtp-window` による窓指定は適用されません（`engine/src/core/mtp.cpp:345-354`）。
- 有効な窓は drafter の attention 対象と K/V 状態メモリの形状に影響します。具体的なメモリ量や性能差はモデル・backend・実行条件に依存し、この調査では測定していません。

## 出力とエラー

- 値が欠けていると parser が stderr にエラーを出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3842-3846`）。
- `--mtp` のロードに失敗した場合は `strata generate: <理由>` を stderr に出して終了コード 1 を返します。batch MTP slot のロード失敗も slot 番号と理由を stderr に出して終了コード 1 になります（`engine/src/program/generate.cpp:8264-8265,8362-8367`）。この引数自体に数値範囲エラーはなく、範囲外値は loader で全セル扱いに正規化されます。

## 根拠

- `engine/src/program/generate.cpp:1036-1038,3842-3846,4055-4057`: 既定値、引数値の取得、型変換。
- `engine/src/program/generate.cpp:8243-8248,8262-8265,8351-8367`: MTP の有効条件と単体・batch drafter への値の転送、ロード失敗経路。
- `engine/src/core/mtp.cpp:511-535,543-547,1342-1349`: CUDA/HIP のリング容量、RAM 不足時の fallback、窓設定と attention。
- `engine/sycl/src/program/generate.cpp:683-685,2049-2051,4525-4547` および `engine/sycl/src/core/mtp.cpp:455-485,1052-1059`: SYCL の既定値、parser、drafter への転送と窓設定。
- `engine/src/core/mtp.cpp:345-354`: Metal build で `window` が使用されない経路。
- `engine/src/program/generate.cpp:14000-14011`: CUDA/HIP の会話設定 fingerprint における値の記録。
