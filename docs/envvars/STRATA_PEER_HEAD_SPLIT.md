# `STRATA_PEER_HEAD_SPLIT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA 系 `NativeHead` の出力 head (`output.weight`) を主 GPU と peer GPU にほぼ半分ずつ置き、native head の推論計算も両 GPU で分担する opt-in 変数。`NativeHead::load` が条件を満たした場合に限って分割し、通常は全 head を現在の GPU に置く。ヘッダーもこの分割状態を P2P 出力 head として定義している（`engine/src/core/native_head.cpp:98-103, 131-136, 149-207`、`engine/include/strata/core/native_head.hpp:45-47`）。

分割候補は `--native-head-gguf` または `--native` から native head が読み込まれる経路で、通常の `--native-head-gguf` には `--stream-token` が必要。さらに peer GPU を指定する必要がある（`engine/src/program/generate.cpp:1260, 5132-5137, 5350-5353, 8320-8329`）。

## 値と判定

`NativeHead::load` のたびに `std::getenv` で取得し、未設定かどうかを確認した後、値全体ではなく `std::atoi(sp) != 0` で判定する。`atoi` が先頭から読める十進整数を変換するため、空文字・整数として読めない文字列・先頭が `0` の値は無効、先頭の整数部分が非ゼロなら有効（例: `1abc`、`-1`、` 1`）。小数や `true` / `false` の文字列としての検査、全体が数値かどうかの検査はない。変換結果の範囲制限や無効値のエラーもない（`engine/src/core/native_head.cpp:132-136`）。

| ビルド / 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `__HIPCC__` と `STRATA_GPU_METAL` のどちらも定義されないビルド | 分割しない | `atoi` 結果が非ゼロ。例: `1`, `-1`, `1abc`, ` 1` | `atoi` 結果が 0。例: 空文字, `0`, `0anything`, `true`, `false`, `abc` |
| `__HIPCC__` または `STRATA_GPU_METAL` が定義されたビルド | 分割しない | 該当なし（分割判定コードがコンパイルされない） | 該当なし |

## 有効になる条件

環境変数が非ゼロでも、次のすべてを満たす場合だけ分割を試みる（`engine/src/core/native_head.cpp:131-140`）。

- `NativeHead::load` が呼ばれる。通常の生成経路では native head が指定され、`multi_gpu` ではないこと。`--native` は head が未指定なら native preset を head にも使う（`engine/src/program/generate.cpp:5132-5137, 8320-8323`）。
- `--peer-device` で有効な別 GPU が指定されており、`peer_device >= 0` かつ現在の GPU (`dev0`) と異なること。既定値は `-1`（`engine/src/program/generate.cpp:913, 1424-1426, 4200`）。peer tier 自体は expert cache と `--expert-profile` を必要とする（同 `10135-10141`）。
- 現在の GPU を `cudaGetDevice` で取得できていること。
- `STRATA_HEAD_HOST` が未設定であること。ここでは値ではなく設定有無を見るため、空文字でも分割を止める（`engine/src/core/native_head.cpp:130, 134`）。
- `strata::kernels::native_q6_k_packed_enabled()` が false であること。`STRATA_Q6_PACKED` が有効な構成では分割しない（同 `135`）。
- `output.weight` がネイティブ MMVQ 対応で正規寸法のテンソルとしてロードされ、出力行数 `n_out >= 2` であること（同 `112-119, 136`）。Q6_K だけに限定する判定はない。
- `STRATA_PEER_NO_P2P` が未設定または `atoi` 結果 0 であること。空文字や `0abc` は分割を止めず、整数部分が非ゼロなら止める（同 `133, 136`）。
- `cudaDeviceCanAccessPeer` が主 GPU → peer GPU と peer GPU → 主 GPU の両方でアクセス可能を返すこと。さらに両方向の `cudaDeviceEnablePeerAccess` が成功すること（既に有効な場合も成功として扱う）（同 `137-149`）。
- `output.weight` の型が Q8_0 (`type == 8`) なら `STRATA_Q8_SM60` が未設定であること。設定値の内容に関係なく、空文字でも分割を止める（同 `135`）。

`--peer-device` は `--layer-split` と併用できず、CLI はその組み合わせを終了コード 2 で拒否する（`engine/src/program/generate.cpp:5256-5262`）。

## 実行時の詳細

変数は `NativeHead::load` のたびに評価され、関数内 static cache はない。通常は生成開始時にロードされ、serve の `--prefill-head-alias` 経路では unload 後の要求処理中に再ロードされることがあるため、その再ロード時にも環境値を読み直す（`engine/src/core/native_head.cpp:98-99, 132-136`、`engine/src/program/generate.cpp:19058-19073`）。

条件を満たすと、出力行を `n_out / 2` 行と残りの行に分け、各部分の重みをそれぞれの GPU に確保して GGUF からコピーする。peer GPU 用の stream、作業領域、logits 領域なども確保する。成功時は `is_split()` が true になり、主 GPU 側と peer 側が出力行の計算を並行して行う。通常の `run` は入力の量子化結果を peer へ送り、peer 側 logits を主 GPU へ戻す。verify 用の `run_verify_split` は各半分の argmax 等を計算して統合する。全 logits が必要な経路向けには `materialize_logits` が peer 側の行を主 GPU 側の連続領域へコピーする（`engine/src/core/native_head.cpp:149-207, 320-345, 436-500`）。

P2P 不可、peer access 有効化失敗、または split 用確保・コピー失敗時には通常の単一 GPU head のロードへ進む。split 用の確保・コピー失敗時は部分リソースを解放してから fallback を試みる。P2P 可否・peer access 有効化失敗ではこの変数専用の警告は出ない。split 用リソース確保またはコピー失敗では次の stderr を出す（`engine/src/core/native_head.cpp:137-149, 185-213`）。

```text
strata generate: STRATA_PEER_HEAD_SPLIT=1 fell back to single-GPU output head (P2P allocation failed)
```

fallback 後の単一 GPU head の確保・アップロードにも失敗した場合、`NativeHead::load` は `native head upload: <CUDA error>` を返し、生成経路はエラーを stderr に出して終了コード 1 で終了する（`engine/src/core/native_head.cpp:241-252`、`engine/src/program/generate.cpp:8323-8325`）。分割成功時には stderr に型、各 GPU の行数・MiB、P2P を示すログが出る（`engine/src/core/native_head.cpp:202-207`）。

## ログと測定値

実装上の成功ログは `strata generate: STRATA_PEER_HEAD_SPLIT=1: split output head (%s) across GPU %d (%d rows, %.1f MiB) and peer GPU %d (%d rows, %.1f MiB) over P2P`。split 用確保・コピーが失敗して単一 GPU に戻った場合のログは「実行時の詳細」に記載したとおり。P2P 可否や peer access の有効化失敗だけでは専用ログを出さない（`engine/src/core/native_head.cpp:137-149, 202-212`）。

`docs/NVIDIA_V100.md:68` は Q6_K head を GPU 0 / peer GPU 1 に分割すると記述しているが、調査対象 commit の実装は Q6_K 限定ではなく、ネイティブ MMVQ 対応型を条件にしている。ここでは当該資料の測定値を一般化せず、現行ソースの挙動だけを記載した。

## 根拠

- `engine/src/core/native_head.cpp:98-149` — load 前提、環境変数読み取り、分割条件、P2P 準備。
- `engine/src/core/native_head.cpp:149-217` — 行分割、GPU ごとの確保・コピー、成功・fallback。
- `engine/src/core/native_head.cpp:320-345, 436-500` — decode / verify の分割実行と結果統合。
- `engine/src/program/generate.cpp:913, 1260, 1424-1426, 4200, 5132-5137, 5256-5262, 5350-5353, 8320-8329, 19058-19073` — CLI、モード、peer device、通常・serve の読み込み経路。
- `engine/sycl/src/core/native_head.cpp:24-27, 109-121` — SYCL の `NativeHead` 実装は `peer_device` を使わず、対象変数の読み取りもない。対象変数を読む CUDA 実装とは分割機能が異なる。
