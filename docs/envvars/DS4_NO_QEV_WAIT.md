# `DS4_NO_QEV_WAIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal runtime の deferred dispatch 経路で、連続する command buffer 間に queue shared event の wait を encode するかを制御します。変数名どおり、設定するとその wait の encode を止めます。未設定時は wait を encode する既定動作です。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | `qev_wait` は `true`。後述の条件を満たせば event wait を encode する |
| 設定あり | `qev_wait` は `false`。値を参照・変換せず event wait を encode しない |

空文字、`0`、`1`、その他の文字列に区別はありません。`std::getenv(...) == nullptr` だけで判定するため、空文字を含む何らかの値が環境に設定されていれば wait を止めます。数値 parse、範囲判定、無効値 fallback はありません。

## 有効になる条件

- `STRATA_DS4_RUNTIME` が定義された Metal runtime のコードであること。対象箇所は `metal/src/mtl_rt.mm` のこの build macro の下にあります。
- `Context::run()` が単一 dispatch、`reps == 1`、`barrier_between == false` の deferred 経路を通ること。
- 新しい deferred command buffer を作る分岐に入ること（open buffer がない、または `def_n >= 2000000`）。
- event wait の encode 自体は、`impl_->qev != nil && impl_->qev_v > 0` の場合に限られます。したがって、最初の deferred buffer の作成時点など、まだ前の buffer が event を signal していない場合は、未設定でも wait は追加されません。

複数 dispatch、複数 repetition、または `barrier_between` が true の呼び出しはこの fast path を通らず、通常の同期実行経路へ進みます。この変数による wait 抑制はその経路には適用されません。CLI 引数や別の環境変数による優先順位・上書きはこの変数の読み取り箇所にはありません。

## 実行時の詳細

環境判定は `Context::run()` 内の関数ローカル `static const bool` で行われるため、最初にこの判定へ到達した時点の環境状態がプロセス内で cache されます。その後の環境変更は反映されません。複数の `Context` があっても同じ static 判定を共有します。

fast path は新しい command buffer を作るとき、値が有効で shared event が存在し signal value が正なら、その buffer に `encodeWaitForEvent` を encode します。deferred buffer の commit 側では `split_runs()` と `flush_runs()` が同じ shared event を signal し、signal value を増やします。環境変数が設定されていると、次の buffer で前の signal を待つ GPU event command の encode だけを省きます。Strata の実装コメントは、同じ queue は command buffer を順番に実行するためこの wait は別 queue 向けの待ちではないと説明し、wait に full GPU round trip がかかるとの注記もありますが、これはコメント上の記述であり、本調査では測定を行っていません。

この変数専用のログ、警告、終了コードはありません。抑制された wait による失敗時の専用処理も確認できませんでした。通常の deferred command buffer 失敗時には `flush_runs()` または `wait_mark()` が stderr に `mtl: deferred command buffer failed: ...` を出す経路がありますが、これは本変数の有無にかかわらない一般の失敗処理です。

## 根拠

- `metal/src/mtl_rt.mm:902-925` — `STRATA_DS4_RUNTIME` 下の `Context::run()` fast path、新規 buffer の条件、`DS4_NO_QEV_WAIT` の unset 判定、event の存在条件、および wait の encode。
- `metal/src/mtl_rt.mm:46-56` — deferred buffer、queue shared event、event value の保持先。
- `metal/src/mtl_rt.mm:796-816,855-895` — `split_runs()` と `flush_runs()` における event signal、buffer commit と一般の失敗ログ。
- `metal/src/mtl_rt.mm:844-852` — mark 待機時の一般の deferred command buffer 失敗ログ。
- `metal/CMakeLists.txt:152-164` — Strata runtime 用 Metal target に `STRATA_DS4_RUNTIME` を定義する箇所。
