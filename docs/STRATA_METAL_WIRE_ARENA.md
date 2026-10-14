# `STRATA_METAL_WIRE_ARENA`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal engine の SSD expert streaming が使う expert arena を、充填後に `mlock` で wire（ページを物理メモリに固定）するか選びます。wire すると GPU が command buffer を実行していない間も arena のページが圧縮対象にならないようにし、代わりに macOS が使える物理メモリを減らします。モデルを resident load する経路や CUDA/HIP/SYCL には、この環境変数を読む実装はありません。

## 値と判定

`metal/src/engine/stream.cpp` の `ExpertStream::make_arena()` が、arena の fill 処理後に環境変数を読みます。空でない値には `std::atoi()` を適用し、その結果が 0 以外なら wire を要求します。文字列全体の厳密な数値検証はありません。

| 値 | wire 要求 |
|---|---|
| 未設定 | 物理 RAM が 64 GiB 以上なら要求、それ未満なら要求しない |
| 空文字 | 未設定と同じ既定判定 |
| `0`、`0abc`、`false`、`abc` | 要求しない（`atoi` 結果が 0） |
| `1`、`2abc`、`-1`、` 1` | 要求する（`atoi` 結果が 0 以外） |

64 GiB の境界は `64.0 * kGB`（`kGB = 1ull << 30`）です。環境変数は static cache されず、arena の各 fill 呼び出しで判定されます。

## 有効になる条件

- `metal/src/engine/window.cpp` で `ExpertStream::wanted()` が true となり、SSD streaming 用 `ExpertStream` が作られていること。`wanted()` はモデル全体が Metal の resident footprint に収まるかを調べ、収まらない場合に streaming を選びます。
- `make_arena()` の fill が空きメモリ不足で途中停止していないこと。途中停止時は未使用 slot の領域まで固定しないよう、wire 処理全体をスキップします。
- 値が wire を要求していること。

設定しても `mlock` 自体が失敗した chunk は固定されません。失敗数は stderr の wire ログに `; SOME CHUNKS COULD NOT BE WIRED` として付加されます。失敗してもこの箇所は arena 作成を失敗扱いにせず、処理を続けます。`mlock` の上限や OS 側の詳細な挙動は Strata のソースだけでは確定できません。

## 実行時の詳細

`Window::init` が streaming 経路を選んだ後、`Window::stream_arena()` から `ExpertStream::make_arena()` を呼びます。arena の expert fill が完了すると、`sysctlbyname("hw.memsize", ...)` で物理 RAM を読み、上記の値判定をします。wire が要求され、fill が途中停止していなければ、各 arena chunk に `mlock(c.ptr, c.bytes)` を呼び、成功分の合計容量と所要時間を stderr に出します。失敗した chunk が一つ以上ある場合は前述の警告句も出力します。

この処理は arena の準備時に行われ、リクエストごとではありません。環境変数を後から変更しても、既に作成された arena の wire 状態は変わりません。このコードで子プロセスへの転送は確認できません。

`docs/MAC.md` は同変数を SSD streaming 向けの設定として説明し、`=0` で arena を pageable のままにし、既定では 64 GB 以上の Mac で wire すると記載しています。同文書には M5 Max でのメモリ圧迫に関する測定記録もありますが、ここではその測定を独立に再現したとは扱いません。

## 根拠

- `metal/src/engine/stream.cpp:542-565` — `mlock` の目的、環境変数の判定、fill 停止時の除外、stderr ログ。
- `metal/src/engine/arena_budget.h:77` — 64 GiB のしきい値。
- `metal/src/engine/window.cpp:425-432,1196-1204` — streaming 経路の選択後に arena を作る呼び出し。
- `docs/MAC.md:108,198` — Mac の streaming 設定と文書上の既定値。
