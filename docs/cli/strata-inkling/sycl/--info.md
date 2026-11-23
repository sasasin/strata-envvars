# `strata-inkling-sycl --info`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl`（SYCL） |
| オプション | `--info` |
| 別名 | なし |
| 値 | 任意のモデルファイルパスを1個。省略した場合は別途 `--model` / `--native` / `-m` で指定する |

## 役割

モデルファイルの Section 0 にある manifest を読み、モデル構成情報を表示して終了する。`--info` 経路は `probe_only` を呼び、通常のモデルロード、runner 初期化、推論処理には進まない。表示項目はアーキテクチャ、物理層数、visit 数、hidden size、vocabulary size、expert 数、EOS ID、D-Spark の有無、vision パス指定の有無、image pad ID、固定値 `parallel=64`、backend と build 情報である（`engine/src/inkling2/sycl/ink_sy_main.cpp:173-180`, `engine/src/inkling2/sycl/ink_sy_common.h:1385-1397`）。

## 使い方

```sh
# --info の直後にモデルファイルを指定
strata-inkling-sycl --info ./model.strata

# モデルパスを明示する標準形
strata-inkling-sycl --model ./model.strata --info
```

`--info` の直後に次の引数があり、その先頭文字が `-` でなければ、その引数をモデルパスとして取り込む。先頭が `-` の場合は取り込まないため、その場合は `--model` で指定する。オプションなしで渡した位置引数をモデルパスとして設定する一般的な処理はなく、ここで示した `--info` 直後の場合に限られる（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-120`）。

## 値と既定値

- `--info` 自体は値を必須とせず、設定値は真偽フラグ `show_info`（初期値 `false`）である。オプションの別名はない（`engine/src/inkling2/sycl/ink_sy_main.cpp:109-110`, `engine/src/inkling2/sycl/ink_sy_main.cpp:119`）。
- モデルパスに既定値はない。`--info <path>` の形では `--info` の直後の非オプション文字列をパスとして設定し、`--model <path>`、`--native <path>`、`-m <path>` でも設定できる（`engine/src/inkling2/sycl/ink_sy_main.cpp:103`, `engine/src/inkling2/sycl/ink_sy_main.cpp:116-120`）。
- parser に拡張子や空文字の検証はない。`--info` の直後にパスがなく、別のモデル指定もない場合は、後段の必須パス確認で usage を stderr に出し、終了コード 1 となる（`engine/src/inkling2/sycl/ink_sy_main.cpp:166-169`）。
- 複数回モデルパスを代入した場合、引数走査中の後の代入が前を上書きする。`--info` の真偽フラグは一度設定されると有効のままである（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-120`）。

## 実行時の動作

1. 起動時に `UR_LOADER_USE_LEVEL_ZERO_V2` が未設定なら、プロセス環境内に値 `0` を設定する。既に設定されている場合は保持する（`engine/src/inkling2/sycl/ink_sy_main.cpp:101-103`, `engine/src/inkling2/sycl/ink_sy_common.h:63-69`）。
2. 引数を走査してモデルパスと `show_info` を設定する。引数走査後に `set_primary_gpu_index` を呼ぶが、この関数はプロセス内の静的 GPU index を設定するだけである（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-145`, `engine/src/inkling2/sycl/ink_sy_main.cpp:164`, `engine/src/inkling2/sycl/ink_sy_common.h:71-78`）。
3. モデルパスが空でなければ `probe_only` がファイルをバイナリ読み込みで開き、先頭 4096 byte を読み、そこから Section 0 の位置・長さを取り出して manifest を読み込む（`engine/src/inkling2/sycl/ink_sy_common.h:1385-1397`）。
4. manifest の値から表示行を出力し、終了コード 0 で終了する。manifest の物理層数、loop 設定から得る visit 数、hidden/vocabulary/expert 数、EOS ID、D-Spark の有無、image pad ID、build 文字列が出力値に使われる。`images` は vision ファイルを読み込んだ結果ではなく、`--vision` による `vision_path` が空かどうかを示す（`engine/src/inkling2/sycl/ink_sy_main.cpp:175-180`, `engine/src/inkling2/sycl/ink_sy_common.h:505-546`, `engine/src/inkling2/sycl/ink_sy_common.h:572-583`）。

`--selfcheck`、`--spec-check`、`--bench`、`--par-sweep` などを併記しても、`show_info` 分岐が通常ロードより前に成功終了するため、それらの後続処理は実行されない（`engine/src/inkling2/sycl/ink_sy_main.cpp:120-124`, `engine/src/inkling2/sycl/ink_sy_main.cpp:171-183`）。

## 適用条件と副作用

- 入力はモデルファイルとして開ける必要があり、先頭 4096 byte と Section 0 の manifest を読める必要がある。重み tensor のロード、SYCL device enumeration、runner 初期化は `--info` 成功経路からは呼ばれない（`engine/src/inkling2/sycl/ink_sy_common.h:1385-1397`, `engine/src/inkling2/sycl/ink_sy_main.cpp:173-183`）。
- オプション自体による出力ファイル作成や書き換えはない。ファイルを読み取り、標準出力に情報を表示する。起動時に前述の環境変数をプロセス内で補う副作用がある（`engine/src/inkling2/sycl/ink_sy_common.h:63-69`, `engine/src/inkling2/sycl/ink_sy_main.cpp:175-180`）。
- `--vision <path>` は `images=1` / `images=0` の表示に影響するが、`--info` 経路では vision モデルや画像をロードしない（`engine/src/inkling2/sycl/ink_sy_main.cpp:117-119`, `engine/src/inkling2/sycl/ink_sy_main.cpp:173-180`, 通常ロード後の vision 処理は `engine/src/inkling2/sycl/ink_sy_main.cpp:185-195`）。

## 出力とエラー

- 成功時は stdout に `strata-inkling 0.1.66` と `arch=... backend=sycl build=...` の行を出し、終了コード 0 で終了する（`engine/src/inkling2/sycl/ink_sy_main.cpp:175-180`）。
- パス未指定時は stderr に Usage 行を出し、終了コード 1（`engine/src/inkling2/sycl/ink_sy_main.cpp:166-169`）。
- ファイルを開けない場合は `cannot open <path>`、先頭 4096 byte を読めない場合は `short header`、Section 0 の読み取り・展開または manifest 解析に失敗した場合はそれぞれのエラー文字列を `[ERROR]` 接頭辞付きで stderr に出し、終了コード 1（`engine/src/inkling2/sycl/ink_sy_common.h:1385-1397`, `engine/src/inkling2/sycl/ink_sy_common.h:469-499`, `engine/src/inkling2/sycl/ink_sy_common.h:502-588`, `engine/src/inkling2/sycl/ink_sy_main.cpp:173-174`）。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-120` — 起動時処理、`--info` の parser、任意パス引数とモデルパス別名。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:146-180` — 引数後処理、必須パス確認、情報表示分岐、出力項目、成功終了。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:183-195` — 通常のモデルロードと vision 読み込みが情報表示分岐の後にあること。
- `engine/src/inkling2/sycl/ink_sy_common.h:63-69`, `engine/src/inkling2/sycl/ink_sy_common.h:71-78` — 起動時の環境変数設定と GPU index 設定。
- `engine/src/inkling2/sycl/ink_sy_common.h:469-499`, `engine/src/inkling2/sycl/ink_sy_common.h:502-588` — Section 0 の読み込み・展開と manifest の値の抽出・解析エラー。
- `engine/src/inkling2/sycl/ink_sy_common.h:1385-1397` — `probe_only` がファイルのヘッダーと manifest を読み、manifest を解析する処理。
