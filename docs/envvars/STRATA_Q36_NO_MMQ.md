# `STRATA_Q36_NO_MMQ`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリ自身が読む環境変数の意味は対象外。

## 役割

Qwen3.6-35B-A3B 用の `strata-q36` エンジンで、prompt 中の routed expert 計算に使う MMQ 経路を無効にします。未設定で、ビルドに MMQ があり、モデル内の全対象 expert weight が対応・適合するときは MMQ 経路を選びます。変数が設定されていれば、MMQ が利用可能でも native grouped kernels を選びます。

この変数は環境変数を読み取る同じ `q36_engine.cu` を使う `strata-q36` と、Qwen3.5 系モデルでそのエンジンへ切り替わる `strata` に適用されます。CMake では `strata_qwen35` を両 executable にリンクしています（`CMakeLists.txt:631-645`）。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | MMQ が build に含まれ、後述の type・device 条件を満たせば MMQ を使用可能 |
| 任意の設定値 | MMQ を無効化。`1` だけでなく、`0`、`false`、空文字列も同じ |

実装は `std::getenv(...) == nullptr` を判定するだけで、値の parse や文字列比較はしません。したがって空文字も「設定あり」です。値を `static` に保存するのではなく `Engine::init()` で `use_mmq` に一度取り込み、その Engine の処理中は保存済みの真偽値を使います。初期化後にプロセス環境を変更しても、その Engine の選択は変わりません。

## 有効になる条件

環境変数が未設定でも、次のいずれかなら `use_mmq` は false です。

- MMQ が build に含まれていない。
- main model の各 layer、または存在する MTP block の gate/up と down の weight type が MMQ の対応 type でない。
- いずれかの weight type と行数の組み合わせが `MMQ::fits()` を満たさない。

これらの条件は `MMQ::built()`、各 layer/MTP に対する `MMQ::supported()` と `MMQ::fits()` の結果を全て累積して判定します。いずれかで失敗すると native grouped kernels に fallback します。変数を設定した場合は、これらの条件に関係なく MMQ を無効にします。

## 実行時の詳細

MMQ が有効なとき、`Engine::init()` は MMQ context と routing・量子化用バッファを確保し、stderr に `strata-q36: prompt experts on MMQ (int8)` と出します。無効なときは MMQ 用バッファを作らず、`strata-q36: prompt experts on the native grouped kernels` と出します。環境変数そのものについての警告やエラーはありません（`src/qwen35/q36_engine.cu:1168-1191`）。

expert 計算で `T > 8`（prompt chunk）の場合、MMQ 経路は routed entry を expert ごとにまとめ、MMQ で gate/up と down の積を実行します。無効時や条件不成立時は `k_group` の後に `K::native_expert_grouped()` を呼びます。`T <= 8` の decode/小 batch はどちらの場合も native grouped 経路を通るため、この変数による routed expert kernel の差はありません（`src/qwen35/q36_engine.cu:1312-1314,1440-1489`）。

expert が VRAM に収まらない hybrid mode では選択差が追加で現れます。MMQ が有効なら大きな prompt chunk で host/slot experts を staging buffer に stream して MMQ に渡す経路を利用します。無効なら `hybrid_t` を `tmax` にし、staging buffer を確保しません。streamed prompt path はなくなり、expert batch は slots と CPU pool の hybrid rows 経路に入ります（`src/qwen35/q36_engine.cu:1079-1082,1450-1489,1514-1518,2031-2035`）。expert placement や decode の一般設定を直接切り替える変数ではありません。

## 文書との照合と根拠

`docs/DETAILS.md` と関連する設計資料を検索しましたが、この変数固有の動作説明や測定値は見つかりませんでした。上記の説明は調査対象 HEAD の実装に基づき、性能差や出力同一性は断定していません。

- `src/qwen35/q36_engine.cu:1168-1191` — 設定有無、build/type/fit 条件、MMQ context 初期化、stderr の選択ログ。
- `src/qwen35/q36_engine.cu:1312-1321,1440-1489` — chunk 閾値と MMQ/native grouped expert 経路。
- `src/qwen35/q36_engine.cu:1511-1518,2031-2035` — streamed prompt と hybrid mode の条件・staging buffer。
- `include/strata/prefill/moe_mmq.hpp:1-32` — MMQ helper の build・対応 type・fit 条件の説明。
- `CMakeLists.txt:631-645` — `strata_qwen35` のリンク先。
