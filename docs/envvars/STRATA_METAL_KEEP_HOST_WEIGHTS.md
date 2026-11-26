# `STRATA_METAL_KEEP_HOST_WEIGHTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal の SSD expert streaming 用アリーナを準備するとき、共通 GPU コードが作った大きな device 側 weight allocation を解放する処理をスキップするか決める。`STRATA_METAL_KEEP_HOST_WEIGHTS` が文字列全体で `"1"` なら保持し、それ以外なら `purge_device_allocations(32 MiB)` を呼ぶ。ここで対象になるのは Metal runtime に登録された 32 MiB 以上の allocation のうち `host_alloc` 由来でないもの。条件に合う allocation は purgeable-empty にされ、residency set から外される。Metal streaming 自体の有効・無効や重みの選択を決める変数ではない。`engine/metal/src/engine/window.cpp:1726-1735`、`engine/metal/src/gpu/runtime.cpp:323-340`。

## 値と判定

`Window::stream_arena` が呼ばれるたびに `std::getenv` で読み、値が存在し、かつ `std::string(value) == "1"` の場合だけ purge を省略する。空文字を含む他の設定値はすべて purge 側となる。数値変換、空白除去、先頭文字判定はない。大文字小文字も区別する。`engine/metal/src/engine/window.cpp:1731-1735`。

| 条件 | unset | 保持する値 | purge する値 |
|---|---|---|---|
| Metal streaming のアリーナ準備時 | purge | `1` | 空文字、`0`、`true`、`01`、`1 ` など `1` と完全一致しない値 |

## 有効になる条件

- Metal の Window が初期化され、`ExpertStream::wanted` が streaming を選び、アリーナ準備の `stream_arena` に到達する必要がある。`STRATA_METAL_STREAM=1` は streaming を選び、`=0` は選ばず、それ以外または未設定ではモデル重みと GPU working set などから自動判定する。したがって対象変数を `1` にしても、streaming が選択されなければこの処理には作用しない。`engine/metal/src/engine/window.cpp:736-744`、`engine/metal/src/engine/stream.cpp:34-49`。
- `stream_arena` は初回の streaming 実行・prompt 経路などで arena が未準備のときに呼ばれる。既に arena が準備済みなら `Window::run` はこの関数を再度呼ばない。`engine/metal/src/engine/window.cpp:1560`、`3039`、`3139`。
- OS / backend 条件はこの Metal 実装を通ること。対象変数を読む処理は `engine/metal` 内にあり、他 backend の読み取り箇所はない。

## 実行時の詳細

環境値は `stream_arena` の開始時、メモリ量の計算と arena 配置より前に評価される。関数内 static や別のキャッシュには保存されない。設定が `"1"` 以外なら runtime の `purge_device_allocations` がまず `device_synchronize` し、32 MiB 未満・既に purge 済み・host allocation の各項目を除いて allocation を purgeable-empty にし、residency set から取り除く。返された合計 byte 数を `strata metal stream: %.2f GB of the host code's device weight copies given back (unused by the Metal window)` と stderr に出す。保持指定時は purge 呼び出しとこの行の出力をともにスキップする。`engine/metal/src/engine/window.cpp:1731-1735`、`engine/metal/src/gpu/runtime.cpp:327-341`。

その後に共通コードが purge 済み allocation を copy の source / destination または fill で使おうとすると、runtime は `strata metal runtime: a %s touches a device allocation of %.1f MB that was given back (STRATA_METAL_KEEP_HOST_WEIGHTS=1 keeps it)` を stderr に出し、backtrace を file descriptor 2 に出力して `std::abort()` する。これは `encode_copy` と `encode_fill` の確認経路であり、環境変数の不正値自体をエラーにする処理ではない。`engine/metal/src/gpu/runtime.cpp:187-202`、`221-226`。

## ログと測定値

測定値は確認できない。purge 側では実際に解放対象になった合計量を GB 単位で stderr に出すが、量は実行時の allocation 集合による。`docs/MAC.md:280` は保持時のコピー量を「2 to 3 GB」と記載するものの、このコードは対象 allocation を 32 MiB 以上に絞っており、その量を固定値として保証していない。`engine/metal/src/engine/window.cpp:1732-1735`、`engine/metal/src/gpu/runtime.cpp:327-340`。

## 根拠

- `engine/metal/src/engine/window.cpp:1726-1735` — 環境値の完全一致判定、purge 呼び出し、stderr の集計行。
- `engine/metal/src/engine/window.cpp:736-744`、`1560`、`3039`、`3139` — streaming 選択後に arena を準備する呼び出し経路。
- `engine/metal/src/engine/stream.cpp:34-49` — `STRATA_METAL_STREAM` による streaming 選択。
- `engine/metal/src/gpu/runtime.cpp:323-341` — 対象 allocation の条件、同期、purge の処理。
- `engine/metal/src/gpu/runtime.cpp:187-202`、`221-226` — purge 済み allocation の copy / fill 時のログ、backtrace、abort。
