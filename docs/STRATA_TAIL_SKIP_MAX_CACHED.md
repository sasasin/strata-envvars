# `STRATA_TAIL_SKIP_MAX_CACHED`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_ROUTE_TAIL_SKIP` が未設定のとき、tail skip の既定有効化を見送る「GPU キャッシュにある専門家の割合」の境界をパーセントで指定します。値が境界以下ならこの変数は tail skip を直接有効にせず、CUDA/HIP の既定有効化条件が別途そろった場合にだけ既定 rank 7 が設定されます。境界以上では既定有効化を抑えます。

この変数は `src/program/generate.cpp` の serve 用 decode 初期化で読みます。tail skip の機能そのものは `STRATA_ROUTE_TAIL_SKIP` によって別に選ばれ、rank 7 などの条件に当てはまる未キャッシュ専門家を、verify window の全 token が低い順位にルーティングしたときにスキップします。

## 値と判定

空でない設定値は `std::atof()` で `double` に変換し、100 で割って割合にします。文字列全体の数値検証や範囲 clamp はありません。したがって数値の後ろに文字があれば `atof` が読める数値部分が使われ、数値に変換できない文字列は 0 として扱われます。空文字または未設定はビルド条件ごとの既定値になります。

| 条件 | `max_cached`（割合） | 判定 |
|---|---:|---|
| CUDA、unset または空文字 | 0.90 | 90% 以上 cached なら「nearly all cached」 |
| HIP、単一 GPU、unset または空文字 | 0.90 | 90% 以上 cached なら「nearly all cached」 |
| HIP、layer split（`n_stages > 1`）、unset または空文字 | 0.60 | 60% 以上 cached なら「nearly all cached」 |
| 非空の数値 `P` | `P / 100` | cached 数が `max_cached * 専門家総数` 以上なら境界以上 |

境界判定は `host_res` が空でなく、全専門家が resident ではない場合にだけ評価されます。全専門家が resident の場合は tail skip 対象となる miss がないため、この境界では扱いません。

値に上下限はありません。例えば `101` なら境界は 101% となり、通常の cached 比率では「nearly all cached」になりません。`0`、負数、数値でない文字列は境界を 0 以下にするため、専門家が一つ以上あり全 resident ではない場合、比較上は「nearly all cached」になります。割合を整数に丸める処理もありません。

## 有効になる条件

この境界が既定 tail skip に作用するのは、`STRATA_ROUTE_TAIL_SKIP` が未設定の場合だけです。`STRATA_ROUTE_TAIL_SKIP` が設定済みなら（空文字も「設定済み」）、キャッシュ率による既定有効化と「キャッシュ率が高いため既定 OFF」の警告は行いません。この場合、rank の有効・無効は `STRATA_ROUTE_TAIL_SKIP` 側の `atoi` と rank 範囲検査で決まります。

未設定時も、tail skip の既定有効化には追加条件があります。

- 全専門家が resident ではない。
- `--batch` が使われていない（`o.batch == 0`）。
- peer GPU がない（`o.peer_device < 0`）。
- `decode_defaults_arch_ok()` が真。CUDA build では常に真、HIP build では現在の GPU が gfx12 WMMA 対応世代（gfx1200 / gfx1201）であること。
- キャッシュ率がこの変数の境界未満。

境界以上で、batch / peer GPU がなく既定対象アーキテクチャなら、stderr にキャッシュ率と「`STRATA_ROUTE_TAIL_SKIP=7` turns it on」を含む既定 OFF の理由が出ます。境界未満なら `set_tail_skip_rank(7)` が呼ばれます。`STRATA_ROUTE_TAIL_SKIP` が明示設定され rank が有効な場合、この境界を超えていても tail skip を使用できます。

## 実行時の詳細

serve の decode 初期化は `host_res` 内の非負 slot 数を数え、`host_res.size()` に対する比率の境界比較を行います。`STRATA_TAIL_SKIP_MAX_CACHED` はここで通常のローカル変数として読み直され、static cache されません。これに対して実際の `STRATA_ROUTE_TAIL_SKIP` rank は `expert_source.cpp` の atomic に初回解決結果を保存します。

tail skip が有効な場合、verify window 内で同じ専門家が全 token に現れ、その全てでのルーティング順位が rank 以上（rank 7 なら 7〜9）で、かつその専門家が GPU cache にないとき、その専門家はコピーも CPU 計算もされず、出力寄与がゼロになります（他の router weight の再正規化はありません）。回答は通常と少し異なり得ます。これは本変数の処理結果ではなく、別変数 `STRATA_ROUTE_TAIL_SKIP` の機能です。

tail skip が使われた場合、request ごとの stderr に累積値 `route tail skip: ... missed experts skipped (... entries) since the start` が出ます。tail skip の既定有効化時には rank と default 表示を含む ON ログが出ます。Strata の `docs/DETAILS.md` には設定時の性能・正確性測定もありますが、ハードウェア、量子化、キャッシュ率などの条件が限定されているため一般性能の保証ではありません。

## 根拠

- `src/program/generate.cpp:1607-1617`: HIP の既定値を適用するアーキテクチャ条件。CUDA は常に許可。
- `src/program/generate.cpp:8279-8315`: resident 数、既定境界（CUDA/HIP 単一 GPU 90%、HIP split 60%）、`atof` による設定読取、境界判定、既定有効化とログ。
- `src/core/expert_source.cpp:3607-3622`: `STRATA_ROUTE_TAIL_SKIP` の初回読み取り、`atoi`、許容 rank 1〜9、および rank 設定。
- `src/core/expert_source.cpp:3691-3712,3725-3729,3825-3827,3865-3868`: window 内の順位条件、miss の skip 判定、コピー・CPU dispatch の省略、出力行のゼロ化。
- `docs/DETAILS.md:1611-1629`: 機能の適用範囲と測定条件、および 90%/60% 境界の説明。現行ソース上の HIP split 既定値は `generate.cpp:8294-8298` の 60%。
