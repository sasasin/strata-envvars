# `STRATA_Q36_READ_WINDOWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen3.6 エンジンのサーバーモードで、進行中の別スロットがあるとき、リクエストの prompt を chunk 単位で読み込む合間に decode window を何回実行するかを指定する。未設定時は 1 回で、値を 0 にすると prompt 読み込み中の合間の decode を止める。値の上限は 64 回。prompt の chunk サイズ自体は変更しない。実装は `Serve::read_windows` と `Serve::request()` にある（`engine/src/qwen35/q36_engine.cu:4735-4741,5136-5149`）。

この環境変数は `--serve` のサーバープロトコル経路でだけ参照される。`strata-q36` の通常の `--tokens` や benchmark 経路は `serve(E)` を通らない（`engine/src/qwen35/q36_engine.cu:5561-5563`）。`strata` の Qwen3.6 切替経路も同じ `strata_qwen35` 実装をリンクする（`engine/cmake/strata_gpu_engine.cmake:565-583`）。

## 値と判定

`Serve` の構築時に `std::getenv` で読み、未設定なら初期値 1 を保つ。設定されていれば `std::atoi` の結果を `std::max(0, std::min(64, ...))` で 0〜64 に制限する。文字列全体の妥当性検証はしない。`atoi` は先頭の空白と符号を受け付け、数字の接頭部分を変換し、数字が始まらない文字列は 0 になる。したがって `4tail` は 4、`0anything`・`true`・空文字は 0、`-1` は 0、`65` は 64 になる（`engine/src/qwen35/q36_engine.cu:4737-4741`）。

| 条件 | unset | 有効になる値 | その他の例と結果 |
| --- | --- | --- | --- |
| Qwen3.6 の `--serve` 経路で `Serve` を構築 | 1 | `1`〜`64`（`+4` や ` 4tail` も変換結果 4） | 空文字、`0`、`0anything`、`true`、`-1` は 0。`65` は 64 に clamp |
| `--tokens` / benchmark など `Serve` を構築しない経路 | 読まれない | 該当なし | この変数による変更なし |

数値として変換できない文字列でもエラーや警告にはならず、0 回として扱われる。`atoi` の変換可能な整数範囲を超えた値の結果は C/C++ ライブラリ上の範囲外入力に依存するため、ここでは保証しない。CLI 引数による上書きはない（`engine/src/qwen35/q36_engine.cu:5348-5413`）。

## 有効になる条件

- 実行経路が Qwen3.6 エンジンの `--serve` であること。Qwen3.6 エンジンは CUDA または HIP 構成で組み込まれ、HIP gfx906 ではこのターゲットを作らない（`engine/cmake/strata_gpu_engine.cmake:565-583`）。
- prompt 読み込み中に別の active slot があること。`--batch` が 1 以下なら decode slot はなく、また BGEN は 2 slot 以上でなければ拒否される（`engine/src/qwen35/q36_engine.cu:1962-1967,5014-5022`）。
- 現在の prompt が最後の chunk に達していないこと。最後の chunk では他 slot の window をここでは実行しない（`engine/src/qwen35/q36_engine.cu:5136-5149`）。

これらの条件が欠けると、値が 1〜64 でも追加の decode window は発生しない。`--chunk`（または `--prefill`）や `STRATA_Q36_CHUNK` は chunk の大きさに関わる別設定であり、この変数は chunk を変更せず、その間の window 数を指定する（`engine/src/qwen35/q36_engine.cu:5361-5364,5517-5518`）。

## 実行時の詳細

読み取りは `serve(E)` が作る `Serve` オブジェクトのコンストラクターで一度だけ行われる。request ごと・chunk ごとの再読込や、この値を保存する static cache はない。設定値は `Serve` の寿命中保持され、実行中の環境変更を再評価するコードはない（`engine/src/qwen35/q36_engine.cu:4737-4741,5332-5335`）。

サーバーは prompt の残りを `Engine::process()` に渡し、各 chunk 完了後の callback で `PP` 進捗行を出す。まだ prompt が残り（`done < fresh`）、active slot がある場合に制御入力を poll してから、`read_windows` 回を上限として `window()` を呼ぶ。各 window は active slot の次 token を処理する。値が 0 ならループは空で、値が正なら slot がなくなるまでその回数分実行する（`engine/src/qwen35/q36_engine.cu:3685-3689,3720-3748,5136-5149`）。通常の chunk callback と生成処理は続き、変数は生成 token の選択規則や prompt の内容を直接変更しない。

各 decode window では `BT <slot> <token>` が出力され、slot が完了すると `BDONE ...` が出力される。要求された回数より先に全 slot が終了すれば追加分は実行されない（`engine/src/qwen35/q36_engine.cu:4912-4945,5140-5144`）。この環境変数の値や clamp 結果を表示する専用ログ、無効値警告、専用の終了経路はない。サーバー開始時の `INFO batch_slots=...` と `READY ...` は出るが、変数値を報告するものではない（`engine/src/qwen35/q36_engine.cu:5281-5285`）。

## ログと測定値

Strata の `docs/QWEN36.md` は、R9700 32 GB、Strata 0.1.45、decode 中の 3 slot という条件で、3,008-token prompt が既定設定では 0.95 秒・6 chunk の読み込み中に各 slot 20 token、`STRATA_Q36_READ_WINDOWS=4` では 1.14 秒の読み込み中に 65 token 生成したと記録している。これは文書に記載された過去の測定値であり、この調査で再測定した値ではない（`docs/QWEN36.md:220-225`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:4735-4741` — 初期値、読み取り方法、clamp、構築時評価。
- `engine/src/qwen35/q36_engine.cu:3685-3689,3720-3748,5136-5149` — chunk 完了 callback と window 実行条件。
- `engine/src/qwen35/q36_engine.cu:4912-4945,5014-5022,5281-5285,5332-5335,5561-5563` — window の出力、batch 条件、serve 起動と対象外経路。
- `engine/cmake/strata_gpu_engine.cmake:565-583` — Qwen3.6 エンジンの CUDA/HIP ターゲットと gfx906 除外。
- `docs/QWEN36.md:220-225` — 条件付きの過去測定値。
