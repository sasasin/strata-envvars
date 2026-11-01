# `STRATA_PF_TILE_DEBUG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の sm_121（GB10 / DGX Spark）で native fused IQ prefill のタイル幅を選ぶ際、その選択内容を stderr に出す診断用環境変数です。タイル幅の選択条件や計算結果そのものは変更しません。

この値を読むのは `src/prefill/moe_fused_iq.cu` の `pick_ww()` だけです。通常の `Batch` 版 native expert 経路から呼ばれた場合に限り、sm_121 で選ばれた `ww` と routed rows / experts / 平均値をログに出します。

## 値と判定

環境変数の文字列全体や数値としての妥当性は検査せず、値が存在し、先頭文字が `'1'` かだけを見ます。`static const bool` に保存するため、最初に `pick_ww()` が強制 tile の早期 return を通過して sm_121 分岐へ入った時点で値が評価され、その後の環境変更は反映されません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効。ログなし |
| 空文字 | 無効。値は設定されているが先頭文字は `\0` |
| `1`, `10`, `1anything` など | 有効。先頭文字が `1` |
| `0`, `true`, ` 1`, `-1`, その他先頭文字が `1` でない値 | 無効 |

無効値に対する警告やエラーはありません。CLI 引数や設定ファイルとの優先順位もありません。

## 有効になる条件

値が有効でも、次の条件が必要です。

- CUDA のデバイス属性が compute capability 12.1（major 12 / minor 1）であること。`dev_info()` は CUDA 側でのみ `s121` を設定し、HIP 側ではこの分岐を設定しません。
- `prefill` が native fused expert 経路を選び、`experts_native(const Batch&)` に到達すること。native 経路の対応可否・有効化は `native_supported()` などで判定されます（`STRATA_PF_FUSED` 等が関与）。native fused を選べない場合は別経路となり、この診断は実行されません。
- `experts_native()` が wide kernel（NT=256 または warp-specialized）用の `WideBatch` 経路を使わないこと。この経路では `pick_ww()` を呼ばず、環境変数も読まれません。

sm_121 の `pick_ww()` は `n >= 65536` なら `ww=2`、それ未満なら `ww=4` を返します。この分岐で環境変数が変更するのはログ出力だけです。`STRATA_PF_FUSED_TILE` は先に `atoi()` で評価され、変換結果が 64 または 128 なら強制幅を返すため、`STRATA_PF_TILE_DEBUG` は読み取られません。`STRATA_PF_FUSED_NT` / `STRATA_PF_FUSED_WS` などによって wide kernel 経路が選ばれた場合も対象外です。

## 実行時の詳細

`prefill.cpp` が `fused_nat` の場合に `fused::experts_native()` を呼びます。`Batch` 版では妥当性確認後、wide kernel を使わない場合に `pick_ww(n, n_expert)` を呼び、その戻り値から gate/up と down の grid サイズを算出して native kernel を起動します。sm_121 の選択分岐では、有効な debug 値があると呼び出しごとに stderr へ次の形式で出力します。

```text
strata: fused tile: rows <n> experts <n_expert> avg <avg> s121 yes -> ww <ww>
```

ログは `fprintf(stderr, ...)` によるもので、環境変数が未設定・無効でも処理失敗にはなりません。診断値はログ以外の処理に使われません。

## 根拠

- `src/prefill/moe_fused_iq.cu:1950-1971` — タイル幅選択、環境変数の先頭文字判定と static cache、stderr のログ。
- `src/prefill/moe_fused_iq.cu:1771-1815` — デバイス情報の cache と、CUDA の compute capability 12.1 判定。HIP 分岐は `s121` を設定しない。
- `src/prefill/moe_fused_iq.cu:2025-2033,2113-2138` — `Batch` 版の native expert 経路、wide 経路の早期 return、`pick_ww()` の呼び出しと tile ごとの launch。
- `src/prefill/prefill.cpp:4307-4320` — prefill から native fused experts または通常 fused experts を選んで呼ぶ箇所。
- `src/prefill/moe_fused_iq.cu:1951-1956` — `STRATA_PF_FUSED_TILE` が有効値なら先に tile 幅を返すため debug 判定を通らないこと。
- `include/strata/prefill/moe_fused_iq.hpp:29-45` — native fused 経路の宣言と `WideBatch` 経路に関する説明。
