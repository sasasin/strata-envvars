# `--hybrid-rows`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` / `strata-q36`（Qwen3.6 専用 parser） |
| オプション | `--hybrid-rows` |
| 別名 | なし |
| 値 | 整数。ハイブリッド実行時に GPU 常駐 expert と CPU pool の並列処理へ送る最大行数を指定する |

## 役割

Qwen3.6 エンジンが expert を VRAM に全て配置できず、CPU expert pool を使うハイブリッド配置になったとき、1回のバッチ処理を GPU 常駐 expert と CPU 側 expert で並列処理する「hybrid rows」経路に回す行数の上限を調整する。これはバッチ全体の大きさではなく、行数に基づく処理経路のしきい値である。

## 使い方

```sh
strata-q36 --model ./model.gguf --hybrid-rows 64 --tokens '1,2,3' --n 16
```

Qwen3.6 のモデル指定と入力例を含む。通常の `strata` が Qwen3.6 family に振り分ける呼び出しでも同じ専用 parser が対象になる。索引では通常エンジンと意味が異なる場合があるため `qwen36/` を独立 scope としている。

## 値と既定値

- parser の既定値は `128`。`--hybrid-rows` を複数回指定した場合は、引数走査で後に現れた値が使われる。
- 値は `std::atoi` で整数化される。parser に独立した数値形式・範囲検査はない。非数値や空文字列は `atoi` の結果 `0` となり、負数と同じく、ハイブリッド配置時に有効なしきい値 `1` へ丸められる。
- CPU pool を使うハイブリッド配置では、指定値を最低 `1`、最高 `E.tmax` に丸める。`E.tmax` は `--chunk` などから渡る処理上限（少なくとも `kVerify`）である。
- `--hybrid-rows` 自体による専用の validation error はない。値がない場合は共通の `next()` が `strata-q36: --hybrid-rows needs a value` を stderr に出し、終了コード `2` で終了する。

## 実行時の動作

引数 parser は値を `hybrid_rows` に読み込み、その値を `place_experts` に渡す。expert が全て VRAM に収まる通常配置では、この値は処理経路のしきい値として使われない。CPU expert pool を含むハイブリッド配置が選ばれた場合、MMQ が有効なら `E.hybrid_t` に丸めた値が設定される。

メイン層がハイブリッドで、処理行数 `T` が `E.hybrid_t` 以下なら、GPU 側の expert と CPU pool の expert を並列に実行して結果を統合する hybrid rows 経路を使う。しきい値を超える prompt chunk は、MMQ が有効な場合、層ごとの expert を staging buffer に stream する経路へ回る。従って、この値は CPU/GPU の担当 expert 数や GPU slot 数を直接指定せず、行数による経路切り替えを制御する。

MMQ が無効な場合は `E.hybrid_t` が `E.tmax` に置き換えられるため、指定値は実質的に使われず、許容されるバッチは hybrid rows 経路に回る。また、メイン層が全て VRAM にあり MTP block だけがハイブリッドのときも、各バッチを hybrid rows 経路で処理する条件になっており、このオプションのしきい値は経路選択に影響しない。

しきい値は実行時の行の割り振りに使われ、VRAM の確保サイズは `E.tmax` 等から別に計算される。値だけを変えても専用のファイル出力やネットワーク動作は発生しない。ハイブリッド配置では、expert をホストメモリに置き、GPU に slot/staging buffer を確保し、CPU pool を起動する副作用があるが、これらは当該配置全体の動作であり、`--hybrid-rows` 固有の副作用ではない。

## 適用条件と副作用

- 有効になるのは、expert が全て VRAM に収まらず、かつ CPU expert pool を含むハイブリッド配置が実際に選ばれる場合に限る。したがって、指定しても配置が通常の全 GPU 配置ならしきい値としては使われない。
- `STRATA_NATIVE_EXPERTS=OFF` 等で CPU pool を含まない build では、全 expert が VRAM に収まれば指定値は実質無関係。収まらなければ `--hybrid-rows` では解決せず、CPU expert pool がない旨のエラーで終了する。
- しきい値超過時の streamed prompt 経路は `use_mmq` が有効であることが条件。MMQ の build・layer 対応状況や `STRATA_Q36_NO_MMQ` が有効性に関わる。
- hybrid rows の設定値で slot 数や VRAM 予算を直接変更する処理は確認できない。配置に必要な VRAM が足りない場合は `not enough VRAM left for the hybrid experts' buffers and slots` のエラー経路があり、`strata::qwen35::run` は配置失敗を stderr に出して終了コード `1` を返す。

## 出力とエラー

ハイブリッド配置が成立すると stderr に expert 配置の要約が出力され、MMQ が有効なメイン層ハイブリッドでは、CPU/GPU が担当するバッチの行上限として `E.hybrid_t` が表示される。オプションの値自体を個別に報告する出力は確認できなかった。値の欠落は終了コード `2`、配置エラーは終了コード `1` となる。

## 根拠

- `src/qwen35/q36_engine.cu:3735-3747` — Qwen3.6 parser と、値欠落時に終了コード `2` で終わる共通 `next()`。
- `src/qwen35/q36_engine.cu:3781` — `--hybrid-rows` を `std::atoi` で読み込む定義。代入のため複数指定では後の値が残る。
- `src/qwen35/q36_engine.cu:2793-2813, 2865-2885` — expert 配置判定、全 GPU 配置時の経路、および CPU pool がない build での失敗。
- `src/qwen35/q36_engine.cu:2887-2917, 2995-3006` — ハイブリッド時のしきい値補正、MMQ 無効時の上書き、VRAM 判定、CPU pool 起動と配置要約。
- `src/qwen35/q36_engine.cu:2009-2074, 2083-2088, 2136-2140` — しきい値による hybrid rows / streamed prompt の切り替えと MTP 側の適用条件。
- `src/qwen35/q36_engine.cu:1339-1345, 1373-1380` — `E.tmax` の下限と MMQ の実行時有効条件。
- `CMakeLists.txt:776-788` — Qwen3.6 engine target と `STRATA_NATIVE_EXPERTS` による CPU pool compile definition。
- `docs/cli/README.md:1318-1339` — 索引上の Qwen3.6 専用 parser scope と、このオプションの予定リンク。

調査は上記 checkout のソースに限定した。既存の同一 revision の `strata-q36 --help` を使った照合や build 構成ごとの実行確認は行っていない。
