# `--vram-reserve-mib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン root 引数） |
| オプション | `--vram-reserve-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数。未指定時は `700`。 |

## 役割

エンジンが VRAM 上の expert cache を見積もる際、他の GPU 利用や起動後の処理に残す領域を MiB で指定します。指定値が大きいほど cache に割り当てられる枠は小さくなります。予約分を別途確保・固定するオプションではなく、空き VRAM と cache・各種バッファの見積もりに使われます。既定値 `700` は `Options` の初期値です（`engine/src/program/generate.cpp:962-963`）。

## 使い方

```sh
# モデルを serve し、cache の自動サイズ計算で 1024 MiB を空けておく
strata --native /models/model.gguf --serve --expert-cache auto --vram-reserve-mib 1024
```

このオプションは `strata-engine` の root parser に登録されています。`--vram-reserve-later-mib` を指定した layer split では、後段 GPU 用 reserve を別に指定できます。

## 値と既定値

- 値は次の argv 要素から `std::atoi` で整数として読み取られ、明示指定フラグも立ちます。短縮別名はありません（`engine/src/program/generate.cpp:3997`）。
- 値を省略すると parser の `next()` が stderr に `--vram-reserve-mib needs a value` を出して終了コード `2` で終了します（`engine/src/program/generate.cpp:3843-3846`）。
- この parser 箇所に範囲検証や形式検証はありません。値の拒否を保証する validation は確認できませんでした。数値以外を渡した場合の変換は `std::atoi` に委ねられます。負数や極端な値を指定した場合の有効性はソース上で保証されていないため、使用値として案内しません。

## 実行時の動作

`--expert-cache auto` では、重みなどを読み込んだ後の空き VRAM から、この reserve、prefill 用バッファ、drafter の head、pipeline の window などを差し引いて cache slot 数を算出します。空き領域があれば、通常は reserve に加えて後続割当て分も見込んで cache を小さくします（`engine/src/program/generate.cpp:9192-9202,9220-9249`; `engine/include/strata/core/auto_cache.hpp:30-44`）。

自動 cache は slot を実際に書き込んだ後にも空き VRAM を読み直します。必要量を下回ると cache を縮めて開き直し、reserve と後続割当て分を満たすまで調整します。cache の確保に失敗した場合、自動 cache は縮小を試み、再試行上限後も確保できなければエラーを stderr に出して終了コード `1` になります（`engine/src/program/generate.cpp:9683-9710`）。

明示的な `--expert-cache N` では、すべての経路が自動 cache と同じ post-write 残量確認をするわけではありません。たとえば native pack の layer split で cache が reserve・prefill buffer と両立しない場合は slot 数を減らす警告が出ます。また、profile に基づく native cache の slot 計算でも reserve を空き枠から差し引きます（`engine/src/program/generate.cpp:9420-9434,9471-9484`）。したがって指定値は最終的な空き容量を常に保証するものではありません。

## 適用条件と相互作用

- layer split の先頭 GPU はこの値を使います。後段 GPU は `--vram-reserve-later-mib` が `0` 以上ならそちらを使い、未指定（内部値 `-1`）ならこの値を引き継ぎます（`engine/src/program/generate.cpp:5870-5890,6084`）。
- reserve を省略した場合の自動調整があります。Windows WDDM の discrete GPU では、自動 cache の安全床まで引き上げる場合があります。明示値は通常維持されますが、`--vision` と既定値 `700` の組み合わせは旧設定との互換経路として例外的に床まで引き上げられます。`STRATA_WDDM_VRAM_FLOOR=0` はこの床を無効化します（`engine/src/program/generate.cpp:9098-9108`; `engine/include/strata/core/low_vram_rules.hpp:58-79`）。
- Windows HIP の自動 cache は、15 GiB 以上の discrete GPU で、明示 reserve がない場合に `2560 MiB` を使います。Linux/TCC の discrete GPU では `--vision` なし、かつ未指定の既定値 `700` の場合に、総 VRAM が 8.5 GiB 以下なら `480 MiB`、12.5 GiB 以下なら `550 MiB` に下げます（`engine/src/program/generate.cpp:9155-9184`; `engine/include/strata/core/uma_cache.hpp:39-43`; `engine/include/strata/core/low_vram_rules.hpp:90-97`）。
- 小容量 GPU で自動 cache が動作に必要な最小 slot 数を満たせないとき、reserve が未指定なら `300 MiB` 以上の範囲で自動的に下げる場合があります。明示指定時はこの縮小経路を通らず、cache 枠不足の診断が出ることがあります（`engine/src/program/generate.cpp:9298-9314,9398-9418`）。
- `--vision --vram-elastic --serve` と resident RAM mode を同時に使う場合、cache を実行中に伸縮できないため、指定値が `2048 MiB` 未満なら reader 用の領域を reserve に含めるよう引き上げます（`engine/src/program/generate.cpp:8975-8984`; `engine/include/strata/core/reader_room.hpp:16-23`）。

## 出力とエラー

自動調整が行われる場合、変更後の reserve と理由を stderr に表示します。自動 cache では計算した空き容量・reserve・slot 数も stderr に出します（`engine/src/program/generate.cpp:9103-9108,9166-9170,9180-9184,9246-9249`）。自動 cache の確保後に空きが不足すれば、実測値と必要量を表示して cache を縮小します（`engine/src/program/generate.cpp:9690-9710`）。

予約量を確保した後に残る VRAM が少ない場合も、serve 起動時に空き容量や「LOW」の警告が出ることがあります。実際の空きは後続割当てや他プロセスにも左右されます（`engine/src/program/generate.cpp:16104-16121`）。

## 根拠

- `engine/src/program/generate.cpp:962-963` — reserve の既定値と明示指定フラグ。
- `engine/src/program/generate.cpp:3843-3846,3997` — 引数値の取得、parser 登録、欠値時の終了。
- `engine/src/program/generate.cpp:5870-5890,6084` — layer split 各 GPU で使う reserve。
- `engine/src/program/generate.cpp:8975-8984` — vision reader と resident RAM mode の補正。
- `engine/src/program/generate.cpp:9098-9108,9155-9184` — Windows WDDM/HIP と low-VRAM の条件分岐および診断。
- `engine/src/program/generate.cpp:9192-9202,9220-9249,9298-9314,9398-9434,9471-9484,9683-9710` — 自動・明示 cache の見積もり、reserve 補正、確保後の縮小・失敗経路。
- `engine/include/strata/core/auto_cache.hpp:30-44`, `engine/include/strata/core/low_vram_rules.hpp:58-97`, `engine/include/strata/core/reader_room.hpp:16-23`, `engine/include/strata/core/uma_cache.hpp:39-43` — cache 計算と reserve 補正 helper。

索引の `strata-engine` root にある `--vram-reserve-mib` と parser のスコープは一致しています。対象 checkout の built CLI help は実行していません。ソースの `usage()` はこのオプションを列挙していないため、この文書は parser と使用箇所を根拠にしています。
