# `STRATA_Q36_STREAM_ALL`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

`strata` が Qwen3.6-35B-A3B (`qwen35moe`) 用エンジンに切り替わった場合、および同じエンジンを使う `strata-q36` で、ハイブリッド実行中にプロンプト用 expert 層を GPU staging buffer へ読み込む方法を変えます。設定すると、各層の expert をすべてホストメモリから GPU にコピーします。未設定時は、VRAM に載っている連続 expert 範囲を device-to-device、VRAM にない範囲を host-to-device でコピーします。ただし VRAM の slot が expert の半数未満なら、未設定でも層全体をホストからコピーする既定経路になります。

これは層のコピー元・転送分割を切り替える変数です。expert 計算の選択や値の parse は行いません。速度への効果はソースからは断定できません。

## 値と判定

| 環境変数の状態 | `all` の値 | 動作 |
|---|---:|---|
| 未設定 | `false` | slot 数に応じて、層全体の host-to-device コピー、または VRAM/ホストの連続範囲ごとのコピーを選ぶ |
| 空文字を含め、何らかの値が設定されている | `true` | slot 数にかかわらず、層全体をホストメモリから host-to-device コピーする |

実装は `std::getenv(...) != nullptr` の設定有無だけを見ます。値を文字列比較・数値変換しないため、`1` 以外に `0`、`false`、空文字なども設定されていれば有効です。無効値や範囲外値という区別はありません。ソースコメントの `STRATA_Q36_STREAM_ALL=1` は使用例ですが、実際の判定は `=1` に限定されません。

## 有効になる条件

この分岐が実行されるのは、Qwen3.6 エンジンで hybrid expert path が使われ、対象層の expert がすべて VRAM slot に収まらず、プロンプト chunk の streamed MMQ 経路が動く場合です。具体的には、MMQ がビルド・型条件を満たして有効であり、main 層の一部が hybrid で、処理行数 `T` が `hybrid_t` より大きいと `forward()` が該当層の stream を開始します。MTP 層にも同じ stream 経路がありますが、その開始条件は `main_hybrid` が真で、MTP 層が hybrid、かつ `T > hybrid_t` であることです。

通常の全 expert VRAM resident 実行では stream を使わないため、この変数は影響しません。hybrid でも `STRATA_Q36_NO_MMQ` の設定などで MMQ が無効の場合、または `T <= hybrid_t` のバッチでは、この層ストリーミング分岐を通りません。decode の1行処理は `T == 1` であり、この分岐ではなく resident GPU と CPU pool の hybrid rows 経路を使います。

## 実行時の詳細

`Engine::stream_kick()` の関数内 static 値として、最初に同関数が呼ばれたとき `getenv()` を評価し、その値をプロセス内でキャッシュします。従って最初の呼び出し後に環境を変更しても再評価されません。warm-up が有効なら `E.warmup()` がリクエスト前にプロンプト処理を行い、この呼び出しで判定されることがあります。warm-up を行わない場合は、最初の該当プロンプト stream で判定されます。

`stream_kick()` は層ごとに2つの staging buffer を交互に使い、コピー用 CUDA stream 上でコピー完了 event を記録します。`all` が真の場合、`L.hblobs` から `L.stride * n_expert` byte 分を一括で host-to-device コピーします。偽の場合は、slot table に基づき、VRAM 内に連続配置された expert 群を device-to-device、slot のない expert 群を host-to-device でそれぞれまとめてコピーします。ただし `2 * L.n_slots < n_expert` なら、`all` が偽でも全層を `L.hblobs` から一括 host-to-device コピーします。

GPU 側は `stream_take()` でコピー完了を待ち、その staging buffer 上の expert weights を MMQ の gate/up と down の計算に使います。`stream_done()` が staging buffer の読み取り完了 event を登録してから、後続層のコピーを開始するため、転送の対象範囲・転送元は変わりますが、この変数自体は別の計算式を選びません。専用のログ出力はありません。

## 根拠

- `src/qwen35/q36_engine.cu:1514-1519,1540-1549`: main / MTP の forward から streamed path を開始する条件。
- `src/qwen35/q36_engine.cu:1570-1575`: sequence 初期化と先頭2層の先行コピー。
- `src/qwen35/q36_engine.cu:1576-1609`: 設定有無の判定、slot 数による既定経路、コピー種別と byte 数。
- `src/qwen35/q36_engine.cu:1610-1624`: copy event 待ち、staging buffer 使用完了、次層の先行コピー。
- `src/qwen35/q36_engine.cu:1447-1482`: hybrid row path と MMQ streamed path の分岐、expert 計算への weights 適用。
- `src/qwen35/q36_engine.cu:1168-1175,2025-2034`: MMQ 利用条件、hybrid mode と staging buffer の設定。
- `src/qwen35/q36_engine.cu:1894-1915,2458-2461`: warm-up が有効な場合の事前実行。
- `CMakeLists.txt:631-645`: Qwen3.6 エンジンを `strata` と `strata-q36` に組み込む設定。

`docs/DETAILS.md` および `docs/INTEL.md` に本変数の説明は見つかりませんでした。コード上の値判定と実行条件を根拠にしています。
