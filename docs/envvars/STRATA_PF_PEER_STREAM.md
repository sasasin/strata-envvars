# `STRATA_PF_PEER_STREAM`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

大きな prompt chunk の expert streaming で、主 GPU がストリームする非 resident expert の一部を peer GPU に転送して計算させます。値は対象 expert の割合を決めます。読み取り箇所は CUDA/HIP 系の `src/prefill/prefill.cpp` と SYCL 版の `sycl/src/prefill/prefill.cpp` です。どちらも `Prefill::set_peer()` の初期化時に読みます。実際に peer を使うには、起動側が `--peer-prefill-rows` を有効にして `set_peer()` を呼ぶ必要があります。

## 値と判定

`std::atof()` で変換し、文字列全体の妥当性検査や範囲制限はありません。

| 設定 | `ps_frac` | 結果 |
|---|---:|---|
| unset | `0.35` | 適用条件を満たせば有効 |
| 空文字、数値に変換できない文字列、`0` | `0` | 無効 |
| 正の数（例: `0.25`, `0.5`, `1`） | その数値 | 適用条件を満たせば有効 |
| 負の数 | 負数 | `ps_frac > 0` の判定で無効 |

`atof()` のため、先頭の空白や数値の後ろの文字列を含む値は、変換できる先頭部分で解釈されます（例: `0.5junk` は `0.5`）。割合を 0〜1 に clamp しません。各対象 expert につき累積値へ割合を加え、1 以上になったときその expert を peer 側へ割り当て、累積値から 1 を引きます。そのため 1 を超える正値も受理されますが、各 expert は一度しか候補にならず、実際に割り当てられる割合は最大でも候補全体です。`nan` のように正数比較が false になる値は有効化されません。

根拠: CUDA/HIP 系 `src/prefill/prefill.cpp:1711-1713,2366-2373`、SYCL `sycl/src/prefill/prefill.cpp:1768-1770,2546-2553`。

## 有効になる条件

- peer prefill の初期化が成功し、compact group buffer が使われる必要があります。CUDA/HIP 系では `STRATA_PF_PEER_COMPACT` が未設定または非0なら compact が有効で、P2P がない場合も compact を強制します。SYCL 版では同変数が未設定または非0の場合に有効です。
- MMQ prompt plan が fallback ではなく、初期化時の最大 chunk `T_max` が `stream_all_min()` 以上である必要があります。閾値は `STRATA_PREFILL_STREAM_MIN` があれば `atoll()` で読んだ値（0 以上の場合）で、未設定または負値なら `g_stream_min_share` が正のときその値、そうでなければ 1024 tokens です。
- 各 chunk の実行時にも、stream ring が通常の staging ring より大きく、chunk token 数 `T` が `stream_all_min()` 以上で、expert source がある必要があります。これを満たさない chunk では peer streaming は行われません。
- SYCL 版は P2P がない peer を `set_peer()` で拒否します。CUDA/HIP 系は P2P がなくても、`STRATA_PF_PEER_HOST` が未設定または `atoi()` の結果が非0なら mapped host memory 経由の peer prefill を許可します。`STRATA_PF_PEER_HOST=0` なら拒否します。
- `STRATA_PF_PEER_RING` は割合が正で、MMQ plan と chunk の初期化条件を満たした場合にだけ読み、peer 用 ring slot 数 `RP` を指定します。既定値は48です。値に範囲検査がないため、0 や負数は安全な slot 数として扱われる保証がありません。

根拠: CUDA/HIP 系 `src/prefill/prefill.cpp:149-153,1697-1716,1803-1812,2302-2314`、SYCL `sycl/src/prefill/prefill.cpp:119-123,1692-1695,1753-1772,2464-2466`。起動側: `src/program/generate.cpp:7368-7373`、`sycl/src/program/generate.cpp:6941-6946`。

## 実行時の詳細

chunk が条件を満たすと、レイヤー・expert ID 順に安定した blob を走査します。source 上で pinned と判定された、peer 自身に常駐していない expert にだけ割合を適用し、選ばれた blob を peer の staging ring に送ります。peer 側はその blob から MMQ group を作り、該当 expert の routed rows を計算します。未選択の expert は従来の主 GPU 側ストリームに残ります。初期化時には stderr に peer GPU、buffer mode、設定割合（丸めた整数パーセント）、ring slot 数を含む `strata prefill: peer GPU ...` 行が出ます。timing が有効な経路では prompt 完了時に peer-streamed expert 数も stderr に出ます。

環境変数は `set_peer()` 呼び出し時に通常のローカル変数として読みます。`ps_frac` は peer prefill object に保存され、chunk ごとに候補 expert の振り分けに使われます。後からプロセス環境を変更しても既存 object の値は変わりません。CUDA/HIP と SYCL の実装は同じ割合の振り分け規則ですが、P2P なしの扱いなど周辺条件は異なります。

根拠: CUDA/HIP 系 `src/prefill/prefill.cpp:1711-1728,1804-1812,2313-2314,2351-2387,3242-3258,3527-3538,4187-4190`、SYCL `sycl/src/prefill/prefill.cpp:1768-1794,1826-1832,2528-2567,3361-3377,3583-3600,4652-4654`。

## 文書・測定値

`docs/DETAILS.md` にこの変数の動作や性能測定の記載は見つかりませんでした。ソースの初期化箇所には、コメントとして `0.25`〜`0.5` が32K tokensで約1950〜1970、`0.35` が最良との記述がありますが、測定環境や指標の説明がその箇所にはないため、一般的な性能値とは扱いません（`src/prefill/prefill.cpp:1712`、SYCL 複製 `sycl/src/prefill/prefill.cpp:1769`）。
