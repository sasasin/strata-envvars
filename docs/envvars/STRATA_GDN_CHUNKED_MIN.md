# `STRATA_GDN_CHUNKED_MIN`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

HIP の gfx12（RDNA4）で、`STRATA_GDN_CHUNKED` が実質 unset のときに、プロンプトの GDN recurrence を WMMA の chunked scan に切り替える入力長の下限 `T` を指定します。既定値は 30,000 です。これはアルゴリズムの chunk サイズではなく、recurrence 全体をその経路に dispatch する前のトークン数の閾値です。通常の GDN prefill がこの選択を通ります。

`STRATA_GDN_CHUNKED` を正の数値にすると gfx11/gfx12 の chunked path を要求し、この下限判定は使いません。負値は `gdn_chunked_env() < 0` の自動選択条件に入るため、unset と同じくこの下限を使います。したがってこの変数単独では gfx11 の既定動作を有効にせず、CUDA の chunked 実装にも適用されません。

## 値と判定

| 環境値 | `lo` の値 | 結果 |
| --- | ---: | --- |
| 未設定 | 30,000 | gfx12 の自動選択は `T >= 30,000` で候補になる |
| 空文字 | 30,000 | 未設定と同じ既定値 |
| 数字を含む文字列 | `std::atoll` の戻り値 | `T >= lo` で判定 |
| 数字に変換できない文字列 | 0 | gfx12 の自動選択で、通常の最低長を満たす呼び出しは閾値を通る |
| 負値 | その負値 | `T >= lo` は通常の正の入力長で成立する |

文字列全体の検証、エラー報告、clamp はありません。`atoll` は数値部分を読み取るため、例えば `12000tail` は 12000 として扱われます。数値の前の空白や符号も `atoll` の変換に従います。オーバーフローの検査もありません。コード上の有効範囲制限はなく、最終的には呼び出し側の最低長 `kGdnWmmaMin`（64）も必要です。

## 有効になる条件

- ビルドが HIP で、実行デバイスが Strata の gfx12 WMMA 対応判定を通ること。CUDA ビルドではこの gfx11/gfx12 dispatch 部分が HIP 条件内にあります。
- `STRATA_GDN_CHUNKED` の `atoi` 値が負（未設定または空文字は `-1`）であること。値が 0 なら無効、正値なら明示要求扱いです。明示した負値も自動選択扱いになります。
- `STRATA_GFX12_DEFAULTS` の先頭文字が `0` でないこと。未設定、空文字、`false` などはこの判定では off になりません。
- GDN recurrence の `T` が 64 以上であること。gfx12 の WMMA 経路はさらに `ld16 % 8 == 0` を要求します。

`STRATA_GDN_CHUNKED=1` など正値を明示した場合は `gdn_chunked_auto()` の下限を参照せず、gfx12 では 64 token 以上の経路判定で進みます。gfx11 も明示要求時は 64 token 以上なら WMMA 経路の候補になりますが、`STRATA_GDN_CHUNKED_MIN` は使われません。`STRATA_GDN_REC_HEADS` が設定されている場合は WMMA recurrence を選ばず、通常の recurrence に進みます。

## 実行時の詳細

最初に `gdn_chunked_auto()` が呼ばれたとき、`STRATA_GDN_CHUNKED_MIN` は関数内の `static const int64_t` として一度だけ読み取られます。`STRATA_GDN_CHUNKED` の変換結果と `STRATA_GFX12_DEFAULTS` の判定もそれぞれ static に cache されます。したがって同じプロセスで後から環境を書き換えても再評価されません。CLI 引数による閾値の上書きはこの実装にはありません。

通常の prefill は `gdn_recurrence()` から recurrence dispatch に入り、HIP では `gdn_rec_wmma()` がデバイス種別、64 token の最低長、chunked 要求／自動選択を確認します。gfx12 で自動選択条件を満たすと WMMA prep と scan kernel を起動し、成功時は通常 recurrence を実行せず戻ります。Fusion が適用される場合も、`gdn_fused_impl()` が同じ `gdn_chunked_auto(T)` を確認します。`STRATA_GDN_FUSE=0` は fusion を無効にしますが、通常の recurrence dispatch 側の gfx12 自動選択までは無効にしません。

条件を満たさない場合 `gdn_rec_wmma()` は `false` を返し、呼び出し元は既存 recurrence 経路へ進みます。通常 recurrence の起動後は `check("gdn_recurrence")` が CUDA/HIP の起動エラーを確認します。閾値自体に対する警告・エラー出力はありません。gfx12 では起動時の arch-defaults 処理が `STRATA_GDN_CHUNKED` 未設定かつ `STRATA_GFX12_DEFAULTS` が off でないとき、stderr に「prompt chunks of 30,000+ tokens use the chunked GDN scan」と出します。このログ文面の数値は固定であり、`STRATA_GDN_CHUNKED_MIN` のカスタム値を反映しません。また、空文字を設定した場合、カーネル側の `gdn_chunked_env()` は未設定相当に扱いますが、arch-defaults のログ条件は環境変数が存在するかを見るため、このログは抑制されます。

## 根拠

- `src/prefill/kernels.cu:1822-1839` — gfx12 の既定閾値、`std::atoll` 読み取り、static cache、自動選択条件、および `STRATA_GDN_CHUNKED` / `STRATA_GFX12_DEFAULTS` との関係。
- `src/prefill/kernels.cu:2133-2168` — 対応デバイス、最低長、stride 条件、gfx12/gfx11 dispatch と WMMA kernel 起動。
- `src/prefill/kernels.cu:2173-2210` — gfx12 fused 経路も同じ自動閾値を使用し、適用できない場合に呼び出し元へ false を返す。
- `src/prefill/kernels.cu:2971-2985,3070-3078,3132-3164` — HIP recurrence dispatch、HEADS による回避、通常経路への継続と起動エラーチェック。
- `src/prefill/prefill.cpp:4216-4257` — GDN prefill が fused 経路または通常 recurrence を呼び出す箇所。
- `src/core/arch_defaults.cpp:270-273` — gfx12 の起動ログ条件と固定文面。
- 関連資料 `docs/AMD_HIP.md:315-324` は gfx11 の opt-in 動作を説明し、`docs/DETAILS.md:1079` は従来の `STRATA_GDN_CHUNKED=1` を記載しています。これらは gfx12 の新しい長さゲートを詳述していないため、上記の現行挙動はソースを根拠にしました。
