# `GPU_PINNED_MIN_XFER_SIZE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata はこの変数の数値を読み取って処理を変えるのではなく、HIP エンジンの起動初期に既存値の有無を確認し、条件を満たしていて未設定なら `1000000` をプロセス環境へ設定する。対象は AMD/HIP のファイルバック arena 経路、または Linux の特定の統合 gfx11 GPU 構成である。設定値そのものの意味や GPU コピーの挙動は ROCm/HIP 側の領域であり、Strata ソースからは確定できない。`engine/src/program/generate.cpp:3736-3757`。

## 値と判定

| 条件 | `GPU_PINNED_MIN_XFER_SIZE` が未設定 | 設定済みの場合 |
|---|---|---|
| `STRATA_ARENA_MMAP` の分岐がコンパイルされ、値の先頭文字が `1` | Strata は `setenv(..., "1000000", 0)` を呼ぶ。既存値があれば上書きしない。 | 値を読み取らず、上書きしない。 |
| Linux の `STRATA_USE_HIP` ビルドで KFD topology が対象クラス | `STRATA_KFD_QUIET` と `STRATA_KFD_QUIET_XFER` が有効なら `1000000` を設定する。 | 値の内容を検証せず、そのままにする。空文字も設定済みとして扱う。 |
| 上記以外 | Strata は設定しない。 | 値の内容を検証せず、そのままにする。 |

`STRATA_ARENA_MMAP` は `getenv` で値が存在し、かつ先頭文字が `1` の場合に分岐するため、`1abc` も条件を満たす。`STRATA_KFD_QUIET` と `STRATA_KFD_QUIET_XFER` は共通 helper が先頭文字 `0` のときだけ無効とし、未設定・空文字・それ以外の値は有効扱いにする。対象変数自身は数値変換も空白除去もされず、`getenv(...) != nullptr` の有無だけで自動設定を抑止する。`engine/src/program/generate.cpp:3742-3754`、`engine/include/strata/core/kfd_quiet.hpp:47-68,251-257`。

## 有効になる条件

- `STRATA_ARENA_MMAP` 経由の設定は `(STRATA_USE_HIP または STRATA_HIP_GFX906) かつ Windows 以外` のビルドで実行され、`STRATA_ARENA_MMAP` の先頭文字が `1` の場合に行われる。ここでは GPU 世代や `STRATA_KFD_QUIET` の値を条件にしない。`engine/src/program/generate.cpp:3736-3744`。SYCL 側の `engine/sycl/src/program/generate.cpp:1858-1866` にも同じ mmap 分岐がある。
- KFD quiet の XFER 設定は `STRATA_USE_HIP` かつ Linux のビルドに限られる。`/sys/class/kfd/kfd/topology/nodes` を読み、GPU node が少なくとも 1 つあり、GPU node がすべて gfx1103・gfx1150・gfx1151 のいずれかなら対象クラスとする。他の GPU node が混在する場合や topology を読めず GPU node が得られない場合は対象外。`engine/src/program/generate.cpp:3745-3753`、`engine/include/strata/core/kfd_quiet.hpp:198-212,228-249`。
- KFD quiet 経由では `STRATA_KFD_QUIET` または `STRATA_KFD_QUIET_XFER` の先頭文字が `0` なら設定しない。いずれか未設定、空文字、先頭文字が `0` 以外ならスイッチ判定上は有効。`engine/include/strata/core/kfd_quiet.hpp:47-68,254-257`。
- `GPU_PINNED_MIN_XFER_SIZE` 自身に CLI 引数や設定ファイルの値を読む処理は見つからない。`--mmap-experts` は引数として別途解析されるが、この変数の直接の読み取り・設定箇所ではない。`engine/src/program/generate.cpp:4213,3742-3754`。

## 実行時の詳細

両方の自動設定経路は engine の `main` で、通常の引数処理や GPU 初期化より前に評価される。`--version` 等の早期終了引数はこのブロックより前に処理される。起動時に一度だけ対象変数の有無を調べ、後段で再読込・キャッシュ更新する Strata コードは確認できない。`engine/src/program/generate.cpp:3696-3744,3745-3764`。

ファイルバック arena 経路は、値が設定済みであるかに関わらず `setenv` を呼ぶが、上書きフラグ `0` により呼び出し元の値を保つ。KFD quiet 経路は topology とスイッチを判定してから対象変数を読み、未設定時だけ同じ値を設定する。mmap 経路が先に値を設定した場合、後続の KFD quiet 経路はその存在を見て追加設定しない。いずれも `setenv` の戻り値を検査せず、失敗時の Strata 独自エラー処理はない。`engine/src/program/generate.cpp:3742-3757`、`engine/include/strata/core/kfd_quiet.hpp:251-257`。

## ログと測定値

KFD quiet 経由で Strata が自動設定し、かつ `STRATA_TRACE` が設定済み（空文字を含む）なら、stderr に `strata trace: kfd quiet: GPU_PINNED_MIN_XFER_SIZE=1000000 (pageable copies staged by the runtime)` を出す。既存値を保持する場合、mmap 経由だけで設定する場合、または KFD quiet 条件が無効の場合に、この箇所から対象変数のログは出ない。警告・終了・失敗を対象変数のために行う分岐は見つからない。`engine/src/program/generate.cpp:3751-3757`。

## 根拠

- `engine/src/program/generate.cpp:3736-3744` — HIP 系、Windows 以外での `STRATA_ARENA_MMAP` 判定と非上書き設定。
- `engine/src/program/generate.cpp:3745-3757` — Linux HIP の topology 判定、設定値の選択、環境設定、trace ログ。
- `engine/include/strata/core/kfd_quiet.hpp:47-68,198-212,228-257` — quiet switch の値判定、対象 GPU node の規則、topology 読み取り、対象変数の未設定判定。
- `engine/sycl/src/program/generate.cpp:1858-1866` — SYCL ソース内の mmap 経由の設定。
- `engine/src/program/generate.cpp:4213` — `--mmap-experts` の引数解析箇所。
