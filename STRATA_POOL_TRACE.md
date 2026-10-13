# `STRATA_POOL_TRACE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

SYCL エンジンの複数トークン検証経路で、CPU expert pool の処理段階を標準エラーに出す診断用スイッチ。expert の割り当てや計算結果を変更せず、pool dispatch 内の進行状況を観測する。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 出力しない |
| 空文字を含む任意の設定値（`0`、`1`、その他の文字列） | 出力する |

`std::getenv(...) != nullptr` の有無だけで判定し、文字列の変換や内容比較はしない。判定結果は関数内の `static const bool` に保存されるため、初回にこのコードへ到達した後の環境変更は反映されない。

## 有効になる条件

- `sycl/src/core/expert_source.cpp` にある `expert_pool_dispatch_multi` が呼ばれたときに適用される。同ソースは SYCL エンジンのビルド対象に含まれる（`sycl/CMakeLists.txt`）。
- この関数は複数トークンの検証ウィンドウ用で、通常の単一トークン dispatch（`expert_pool_dispatch`）にはこのトレースはない。
- 複数 GPU の layer split を使う場合も、`drive_pool_split` が各層の設定を選んで `drive_pool_multi` に委譲するため対象になる。
- 先行する入力検査で失敗して関数が戻る場合、または呼び出し自体がない場合は出力されない。トレース判定は入力検査後に行われる。

## 実行時の詳細

有効時は各呼び出しで、stderr に `pool trace: layer <層番号> <段階> <整数>` を出し、直ちに flush する。記録する段階は次のとおり。

- `begin`（整数は既定値 `-1`）: source の層開始処理の直前。
- `begun`（`-1`）: source の層開始処理の直後。
- `publish <fetches>` と `fetch <fetches>`: GPU plan が利用可能な経路で、それぞれ plan 公開・fetch 開始の直前。plan がない経路ではこの2行は出ない。
- `run <njobs>`: CPU pool のジョブ実行直前。`njobs` は組み立てた CPU expert job 数。
- `ran`（`-1`）: CPU job の実行と remote/peer の完了処理の後。

ログは時間計測値や個々の expert ID を含まず、これらの段階まで処理が進んだことを示す。トレースの出力は処理制御や pool の結果を変えない。コード上、環境変数を子プロセスへ転送する特別な処理はない。

## 根拠

- `sycl/src/core/expert_source.cpp:2547-2577`: 対象関数、入力検査、環境変数の有無判定と `begin` / `begun` の出力。
- `sycl/src/core/expert_source.cpp:2670-2679`: GPU plan が有効な場合の `publish` / `fetch` 出力。
- `sycl/src/core/expert_source.cpp:2711-2737, 2785-2812`: CPU pool job 数、`run` / `ran` の位置と dispatch 完了処理。
- `sycl/src/program/generate.cpp:1002-1020, 1038-1049, 7207-7209, 12359-12375`: 検証窓からの呼び出し、および layer split 経路。
- `sycl/CMakeLists.txt:220-227`: `expert_source.cpp` を含む SYCL engine ソースの構成。
- `docs/DETAILS.md`: 関連する CPU expert pool の説明はあるが、この変数名やこのトレース形式の説明は見つからなかった。
