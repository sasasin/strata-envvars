# `--expert-cache-per-layer`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン。Terminal CLI とは別プログラム） |
| オプション | `--expert-cache-per-layer` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

expert cache の空き slot を全 layer 共有の到着順で割り当てる代わりに、layer ごとの固定範囲から割り当てます。これにより一部の layer が先に cache 全体を使い切ることを避けます。既定では無効です（`src/program/generate.cpp:564-569`; `include/strata/core/expert_cache.hpp:167-183`）。

## 使い方

```sh
strata generate --pack /path/to/model.pack --tokens "1,2,3" \
  --expert-cache 256 --expert-cache-per-layer
```

`--expert-cache-per-layer` は値なしで指定します。`--expert-cache` は cache 容量を有効化する別オプションです。エンジンの usage は `strata generate --pack DIR --tokens ...` 形式です（`src/program/generate.cpp:806-812`）。

## 値と既定値

parser はフラグを受け取ると内部値を `true` にします。省略時の初期値は `false` で、個別の値検査はありません。同じフラグを複数回指定しても `true` のままです（`src/program/generate.cpp:569,2742`）。値を続けて指定する構文はなく、後続の値は別引数として処理されます。

このフラグだけでは cache を有効にしません。`expert_cache` が正のときだけ cache 初期化後に per-layer admission が設定されます（`src/program/generate.cpp:6415-6419`）。

## 実行時の動作

cache の slot 数を `S`、model の layer 数を `L` とすると、各 layer の基本 quota は `q = floor(S/L)` です。layer `l` は `[l*q, (l+1)*q)` の範囲を使い、余りは最後の layer が受け取ります。layer 内で未登録 expert が初めて要求されたとき、その layer の次の空き slot に登録します。同じ expert の再要求は既存 slot を返します。範囲が満杯なら、その layer から新たな expert は cache に入らず、eviction も行われません（`src/core/expert_cache.cpp:627-660`; `include/strata/core/expert_cache.hpp:178-183`）。

expert profile がある場合は profile 順に事前充填します。per-layer 時は profile 全体を走査し、満杯の layer の項目を飛ばして他 layer の quota も満たす処理です（`src/program/generate.cpp:6441-6454`）。

native pack では slot のサイズが layer ごとに異なるため、`--expert-cache N` の予算は引き続き最大 blob `N` 個分を基準にします。per-layer 指定時は GPU 空き容量と `--vram-reserve-mib` を差し引いた予算内で全 layer に同数の slot が入る quota を計算し、各 layer 自身の blob サイズで slot を構成します。従って実 slot 数は `N` と異なり、空き VRAM や layer 数により要求より小さくなります（`src/program/generate.cpp:6222-6253`）。native pack 以外ではこの native 専用のサイズ再計算分岐は通らず、cache の既存 slot 数を layer 範囲に分けます。

## 適用条件と副作用

- 効果があるのは GPU expert cache が実際に有効なときです。`--expert-cache` が省略され、profile もなく初期値 `0` のままの場合は cache が作られず、このフラグによる admission 設定・表示は行われません。profile があると `--expert-cache 0` は自動サイズ扱いになり得るため、最終的に cache が正の slot 数で有効になった場合に適用されます（初期値: `src/program/generate.cpp:550-558`; cache 有効条件: `src/program/generate.cpp:6415-6419`）。
- slot の割当範囲を分割するため、均等割り切れない場合でも最後の layer が余りを保持します。特定 layer の需要が quota を超えた場合、他 layer に空きがあってもその空きを使えず、超過 expert は cache に入りません（`src/core/expert_cache.cpp:629-655`）。
- eviction は追加されません。profile がない場合は実行中に到着した expert で各 layer の枠が埋まります。profile がある場合は profile で選ばれた expert が優先的に事前登録されます（`src/program/generate.cpp:6435-6451`; `src/core/expert_cache.cpp:647-660`）。
- cache 内の expert は GPU で計算されるため、CPU 計算とは浮動小数点の丸め順序が異なり、出力がわずかに異なる場合があるとエンジンは stderr に案内します。この注意は per-layer フラグ固有ではなく、cache を有効にした場合のものです（`src/program/generate.cpp:6420-6429`）。

## 出力とエラー

cache が有効なら stderr に cache の slot 数・VRAM 使用量を出力し、このフラグが有効な場合は per-layer policy と layer 0 の slot 範囲も表示します（`src/program/generate.cpp:6415-6434`）。このフラグ固有の validation error はありません。未知の引数は `unknown argument` と usage を stderr に出して終了コード `2` になります（`src/program/generate.cpp:2787-2792`）。cache の確保に失敗した場合の診断・縮小処理は一般の expert-cache 初期化経路に属し、本オプション単独の検証エラーではありません（`src/program/generate.cpp:6367-6413`）。

## 根拠

- 索引との照合（文書リポジトリ）: `docs/cli/README.md:1128-1178`
- 値なし parser と既定値: `src/program/generate.cpp:564-569,2742`
- per-layer slot 範囲、quota、eviction なしの admission: `include/strata/core/expert_cache.hpp:178-186`; `src/core/expert_cache.cpp:627-660`
- native pack の予算・layer 別 blob サイズによる再計算: `src/program/generate.cpp:6222-6253`
- cache 有効時の設定、警告、policy 表示、profile 事前充填: `src/program/generate.cpp:6415-6454`
- unknown argument の失敗経路: `src/program/generate.cpp:2787-2792`

調査範囲は上記 commit の checkout 内ソースです。Release 配布バイナリや実機上の backend ごとの挙動は確認していません。性能値は本調査では測定していません。
