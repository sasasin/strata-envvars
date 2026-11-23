# `STRATA_METAL_KEEPALIVE_WINDOW_S`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal runtime の GPU keep-alive を、最後の通常 command buffer から何秒間続けるかを指定する。正の値なら、アイドル中に短い GPU command buffer を定期投入して Context が追跡する Metal buffer を `useResource` で参照し、値を超えてアイドルになった後は keep-alive を行わない。GPU keep-alive の実装は `mtl::Context::Impl::start_keepalive()` にあり、モデル計算や生成処理そのものの設定ではない（`engine/metal/src/mtl_rt.mm:44-53,76-119`）。

## 値と判定

`start_keepalive()` が `std::getenv` で文字列を取得し、未設定または空文字なら `120.0` 秒を使う。それ以外は `std::atof` で `double` に変換する。変換エラーの検査、範囲 clamp、全体文字列の妥当性検査はない。したがって数値として読める先頭部分を変換し、後続文字は判定に使わない。`win > 0` のときだけ機能を続行するため、0・負数・数値に変換できない文字列は無効（停止）になる。先頭空白は `atof` の変換規則に従い、`true` は数値に変換できず無効。`1tail` は `1` として有効、`0anything` は `0` として無効になる（`engine/metal/src/mtl_rt.mm:80-82`）。

| 条件 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_METAL_KEEPALIVE_MS` が正 | 120 秒 | `1`, `1tail`, `0.5` など、`atof` 結果が正の値 | `0`, `0anything`, `-1`, `true`, 空白だけなど、変換結果が正でない値 |
| `STRATA_METAL_KEEPALIVE_MS` が未設定・空・変換結果が 0 以下 | この変数は読み取られず、keep-alive 自体が停止 | 該当なし | この変数の値にかかわらず停止 |

`atof` の後に `win > 0` を判定するだけなので、正数に上限はありません。`atof` が正の無限大を返す表記もこの判定は通り、idle 比較では窓が期限切れになりません。NaN は正数判定を満たさず停止します。空文字を明示した場合は unset と同じく 120 秒です（`engine/metal/src/mtl_rt.mm:77-82`）。

## 有効になる条件

- Metal runtime の `mtl::Context` が生成され、デフォルト Metal device を取得できること。デバイスがなければ変数評価以前に `mtl: no Metal device` を stderr に出して終了コード 2 で終了する（`engine/metal/src/mtl_rt.mm:139-147`）。
- 先に読まれる `STRATA_METAL_KEEPALIVE_MS` が正であること。未設定・空文字は 250 ms、設定時は `atof` の結果を使い、正でなければこの関数は window 変数を読む前に戻る（`engine/metal/src/mtl_rt.mm:76-82`）。このため interval 側を 0 以下にすると、本変数を設定しても keep-alive は動かない。
- window の変換結果が正であること。0 以下では thread を作らず、成功ログも出ない（`engine/metal/src/mtl_rt.mm:80-83`）。
- keep-alive 用 MSL kernel と 256 byte の shared buffer の作成が成功すること。kernel または buffer が作れない場合は stderr に `mtl: the GPU keep-alive kernel did not build; keep-alive off` を出して戻る（`engine/metal/src/mtl_rt.mm:84-92`）。
- thread が動作中であり、macOS がメモリ圧力状態でないこと。`kern.memorystatus_vm_pressure_level` が取得でき、値が 1 より大きい場合はその周期を飛ばす。sysctl の取得に失敗した場合は圧力ありとは判定しない（`engine/metal/src/mtl_rt.mm:71-75,94-100`）。

OS/backend の条件は macOS の Metal runtime の実装に限られる。`mtl_rt` は Metal framework をリンクするライブラリで、engine を含む Metal build ではその runtime が利用される。また同じライブラリをリンクする Metal の standalone kernel プログラムでも `Context` を作れば対象になる。CPU/CUDA/HIP/SYCL の実装はこの読み取りを行わない（`engine/metal/CMakeLists.txt:1-20,34-41,82-99,168-180`; `engine/metal/src/mtl_rt.h:79-82`）。CLI 引数、モデル状態、他の環境変数による window 値の上書きはない。関連する `STRATA_METAL_KEEPALIVE_MS` は機能全体の有効化と周期を決める。

## 実行時の詳細

値は `Context` のコンストラクタ内で `start_keepalive()` を呼んだ時に一度読み、`ms` と `win` を thread に値コピーする。以後の環境変数変更は既存 `Context` に反映されない。コンストラクタは `last_commit` を現在時刻で初期化してから keep-alive を開始する（`engine/metal/src/mtl_rt.mm:54-60,139-150`）。通常 command buffer の commit では `touch()` が時刻を更新する（例: `engine/metal/src/mtl_rt.mm:437-455,459-484,488-500,517-555,559-576,583-631`）。

thread は `ms` 間隔で sleep し、終了フラグ、最後の commit からのアイドル時間、メモリ圧力を確認する。アイドル時間が `ms` 未満、`win` 秒を超過、または圧力ありならその回は何もしない。それ以外では main command queue に kernel command buffer を commit して完了を待つ。この keep-alive command buffer 自身は `last_commit` を更新しない。`all` に登録された Context の Metal buffer を encoder に `useResource(..., MTLResourceUsageRead)` で渡す。buffer は alloc/wrap 時に追跡され、Context の `free()` で追跡解除される（`engine/metal/src/mtl_rt.mm:61-69,94-115,299-318,321-398,400-412`）。

Context の破棄時には停止フラグを立て、thread が終了するまで join する。thread は sleep の後に停止フラグを確認するので、破棄は現在の sleep の終了を待つ場合がある（`engine/metal/src/mtl_rt.mm:94-97,153-156`）。この変数は keep-alive を続けるアイドル時間の窓であり、CLI timeout や command buffer の待ち時間を変更しない。

## ログと測定値

window と interval が正で kernel/buffer の作成が成功すると、stderr に次の成功ログを出す。window が 0 以下、または interval が無効ならこのログは出ない。

```text
mtl: GPU keep-alive every %.0f ms for %.0f s after the last command buffer (#6078; STRATA_METAL_KEEPALIVE_MS=0 turns it off)
```

kernel または buffer の作成失敗時は前述の stderr 警告を出し keep-alive を開始しない。Strata の `docs/DETAILS.md` に本 GPU keep-alive の条件付き測定値は見つからず、ここでは速度効果を記載しない。実装コメントには #6078 の測定メモがあるが、これは本調査で再測定した値ではない（`engine/metal/src/mtl_rt.mm:44-53,84-92,117-119`）。

## 根拠

- `engine/metal/src/mtl_rt.mm:44-53,54-82` — 目的、既定値、interval との順序、値変換と正数判定。
- `engine/metal/src/mtl_rt.mm:71-119` — 圧力判定、kernel 作成、keep-alive thread、commit 条件、ログ。
- `engine/metal/src/mtl_rt.mm:139-156` — Context 生成時の評価と破棄時の thread 停止。
- `engine/metal/src/mtl_rt.mm:299-412` — 対象 Metal buffer の追跡と解除。
- `engine/metal/CMakeLists.txt:1-20,34-41,82-99,168-180` — macOS 限定の Metal runtime と engine/standalone target の build 範囲。
- 候補名の全参照を検索し、実読み取りは `engine/metal/src/mtl_rt.mm:80` のみと確認した。`terminal/data/settings-register.json:21079-21089` にも名前があるが、これは設定メタデータであり、環境から値を読む実装ではない。
