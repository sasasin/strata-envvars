# `STRATA_DF2_ATTN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 DFlash2 drafter の attention kernel variant を選びます。環境変数を読むのは `sycl/src/kernels/cuda/dflash2.dp.cpp` だけです。CUDA 版 `src/kernels/cuda/dflash2.cu` は bench 用の variant 変数を持ちますが、この環境変数は読みません（同ファイル:22,960-996）。したがって、CUDA backend でこの変数を設定しても Strata 側の DFlash2 kernel 選択は変わりません。

SYCL kernel では値 `2` が 256 work-item の実装を選び、それ以外の通常経路は 128 work-item の実装を選びます。未設定時のビルド既定値は `DF2_ATTN_AUTO`（このソース内の既定値 `2`）なので、標準の SYCL build では 256 work-item variant です。

## 値と判定

値は `std::atoi` で整数に変換され、文字列全体の妥当性検査はありません。変換結果が 0 かどうかで既定値へ切り替え、選択分岐では値が正確に `2` かだけを調べます。

| 環境値 | 判定後の variant |
|---|---|
| 未設定 | `DF2_ATTN_AUTO`。ソースの既定は `2` |
| 空文字、非数値で始まる文字列、数値変換結果が `0` | `DF2_ATTN_AUTO`（既定 `2`）|
| `2`（または `atoi` 結果が `2` になる文字列） | 256 work-item kernel |
| `1` | 128 work-item kernel |
| その他の 0 以外（負値を含む） | 128 work-item kernel |

たとえば `2junk` は `atoi` 結果が 2 なので variant 2、`1junk` は variant 1 相当、`junk` は変換結果 0 なので既定 variant 2 になります。負値や 3 などもエラーにはならず、variant 2 以外の分岐（128 work-item）に入ります。根拠: `sycl/src/kernels/cuda/dflash2.dp.cpp:34-35,191-199,336-342`。

## 有効になる条件

- この読み取りは SYCL の DFlash2 attention kernel に限られます。SYCL ソース先頭は Intel Arc 向け実装と記載し、CUDA 実装には同名の `getenv` がありません（`sycl/src/kernels/cuda/dflash2.dp.cpp:1-2,194-199`; `src/kernels/cuda/dflash2.cu:17-22,960`）。
- 実行経路が DFlash2 を呼び出す場合に限り評価されます。SYCL `Dflash2Drafter::record_block()` は各 layer の処理で `df2_attention()` を呼びます（`sycl/src/core/dflash2.cpp:379-399`）。通常の `--draft dflash2` 経路では、起動引数・pack・spec の条件を満たし、単一 GPU・非 batch・非 pipeline でロードされる必要があります（`sycl/src/program/generate.cpp:4370-4380,4423-4433`）。
- ビルド時に `DF2_ATTN_AUTO` を別途定義した場合は `#ifndef` の既定値 2 が置き換わります。リポジトリ内では同 macro の別定義は見つかりません（`sycl/src/kernels/cuda/dflash2.dp.cpp:31-35`）。
- `df2_attention_variant()` による非ゼロの内部 override があれば、環境値より優先されます。ただし宣言は bench 用で、リポジトリ内の呼び出しは benchmark code にあります（`include/strata/kernels/dflash2.hpp:59-63`; `sycl/src/kernels/cuda/dflash2.dp.cpp:735-737`; `sycl/src/kernels/dflash2_bench.cpp:450-451,683-687`）。通常の `generate` / `serve` DFlash2 初期化経路ではこの setter を呼んでいません。

## 実行時の詳細

`df2_attention()` の最初の呼び出しで lambda が `std::getenv("STRATA_DF2_ATTN")` と `std::atoi` を実行し、その結果を関数内の `static const int env_v` に保存します。以降、このプロセスで環境を変更しても再読込されません。実際の variant は毎回、非ゼロの bench override、非ゼロの保存済み環境値、`DF2_ATTN_AUTO` の順で決まります（`sycl/src/kernels/cuda/dflash2.dp.cpp:191-199`）。

variant 2 は 256 work-item の SYCL kernel launch、その他は 128 work-item の launch です。両分岐の後に共通の部分結果集約と量子化を行います（`sycl/src/kernels/cuda/dflash2.dp.cpp:199-205,336-342,471-490`）。`STRATA_DF2_ATTN_CHUNK` は別に読み取られ、work-group が処理する key 数を選びます。これは attention variant の値判定とは独立です（同ファイル:196-198）。

この変数に対する専用ログ、無効値警告、範囲チェックはありません。したがって不正な文字列は `atoi` 結果に応じて既定 variant に落ち、variant 選択だけを理由とする Strata のエラー終了経路はありません。kernel 実行時の backend エラーについて、この環境変数固有のエラー処理は確認できません。

## 根拠

- 環境値の唯一の読み取り、変換、cache、優先順位、variant 分岐: `sycl/src/kernels/cuda/dflash2.dp.cpp:191-199`。
- 128/256 work-item kernel 分岐と後段の共通処理: `sycl/src/kernels/cuda/dflash2.dp.cpp:199-205,336-342,471-490`。
- DFlash2 実行経路からの呼び出し: `sycl/src/core/dflash2.cpp:379-399`; 起動条件: `sycl/src/program/generate.cpp:4370-4380,4423-4433`。
- Bench override API と使用例: `include/strata/kernels/dflash2.hpp:59-63`; `sycl/src/kernels/cuda/dflash2.dp.cpp:735-737`; `sycl/src/kernels/dflash2_bench.cpp:450-451,683-687`。
- CUDA backend が同名環境変数を読み取らないこと: `src/kernels/cuda/dflash2.cu:17-22,960-996`。
