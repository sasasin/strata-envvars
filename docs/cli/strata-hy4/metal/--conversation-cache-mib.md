# `strata-hy4-metal --serve --conversation-cache-mib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal --serve` |
| オプション | `--conversation-cache-mib` |
| 別名 | なし |
| 値 | `atoi` で整数に変換する MiB 数 |
| 調査時の checkout 状態 | `## main...origin/main`（未コミット変更なし） |

## 役割

`--session-reuse 1` で serve する際に、会話ごとの Metal KV セットを何 slot 分まで常駐させるかを制限するための容量値です。実際の slot 数はこの MiB 数だけでなく、1 slot の KV セットの大きさと `--conversation-slots` にも制限されます。MiB 数が1 slot 分に満たなくても1 slotは残るため、厳密なメモリ上限ではありません。`--cold-experts` が有効な場合には、追加 slot と spill 用 KV セットの見込み分を cold-expert LRU cache の予算から差し引く計算にも使われます。

## 使い方

```sh
# serve で常駐会話 KV の slot 予算を 8192 MiB に設定する
strata-hy4-metal --model ./SQ64.strata --serve --session-reuse 1 --conversation-cache-mib 8192
```

## 値と既定値

- 値は `atoi` で整数に変換されます。初期値は `16384` MiB（16 GiB）です。Metal 固有 parser に明示的な範囲検査や変換エラー検査はありません。非数値文字列や桁あふれを含む入力に対する値の扱いは `atoi` に依存します。オプションを複数回指定した場合は parser の代入が後の値で置き換わります。【`engine/src/hy4flash/metal/hy4_metal_main.cpp:1495`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1595`】
- `--session-reuse` が有効な serve では、常駐 slot 数を概ね `min(--conversation-slots, floor(値 × 1,048,576 / KVセット bytes))` として計算し、最低1に補正します。MiB 値が0または負数でも slot 数は0にはなりません。【`engine/src/hy4flash/metal/hy4_metal_serve.h:262-266`】
- `--conversation-slots` を正数で指定しなければ、`--session-reuse 1` のときの上限 slot 数は4です。再利用が無効なら既定値は1です。【`engine/src/hy4flash/metal/hy4_metal_main.cpp:1647-1650`】

## 実行時の動作

parser は値を `conv_mib_arg` に読み込み、`--serve` 分岐で `ServeOpts::conv_mib` に渡します。serve 初期化では `--session-reuse` が有効な場合だけ slot 計画と `plan_conv_mib` に反映されます。再利用が無効なら常駐 slot 数は1で、この値は slot 計画に使われません。【`engine/src/hy4flash/metal/hy4_metal_main.cpp:1595`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1654`, `engine/src/hy4flash/metal/hy4_metal_serve.h:227-232`, `engine/src/hy4flash/metal/hy4_metal_serve.h:262-266`】

KV セットの大きさは各層の SWA ring または sparse cache に加え、非SWA層の index と pooled buffer を合算して求めます。従って、同じ MiB 値でも `--ctx`、モデル構成、ring 設定などで slot 数は変わります。【`engine/src/hy4flash/metal/hy4_metal_main.cpp:379-396`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:614-618`】slot の器は `eff_slots` に応じて確保されますが、追加 KV セットは slot が初めて選ばれたときに割り当てられます。会話の選択では常駐可能数に加えて再利用条件を見て、空き slot または LRU slot を使います。【`engine/src/hy4flash/metal/hy4_metal_serve.h:263-285`, `engine/src/hy4flash/metal/hy4_metal_serve.h:375-404`, `engine/src/hy4flash/metal/hy4_metal_slots.h:35-67`】

`--cold-experts` が有効な場合、serve はこの値を負数なら0にした `plan_conv_mib` として Runner に渡します。Runner の cold-expert cache 予算計算では、追加 slot の見込み KV bytes と、有効な SSD spill tier があればその予備セット分を差し引きます。`STRATA_METAL_EXP_CACHE_GB` が設定されている場合も、その環境変数で基礎予算を置き換えた後に差し引きます。ただし予算は最終的に少なくとも1層分（512 expert slots）へ引き上げられるため、差し引きが常にそのまま最終 cache 容量になるとは限りません。【`engine/src/hy4flash/metal/hy4_metal_serve.h:227-232`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:637-659`】

## 適用条件と副作用

- この値の実行時効果は `--serve` 経路に限られます。`--load-only` は serve 分岐より先に終了し、通常の offline 実行経路にも `conv_mib_arg` の使用箇所はありません。【`engine/src/hy4flash/metal/hy4_metal_main.cpp:1595`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1654`】
- slot の容量計算を有効にするには `--session-reuse` が必要です。画像要求は会話 KV の再利用対象外ですが、serve 全体の slot 上限の計算自体は維持されます。【`engine/src/hy4flash/metal/hy4_metal_serve.h:263-276`, `engine/src/hy4flash/metal/hy4_metal_serve.h:375-382`】
- spill は `--session-reuse` が有効で、spill root が空でなく、`--conversation-spill-mib` が正数のときに起動します。root は `--conversation-spill-dir` の明示値、またはモデルパスに `/models/` がある場合の既定場所から決まります。spill 用に常駐 slot 数とは別の KV セットを1個使える上限が設けられます。【`engine/src/hy4flash/metal/hy4_metal_spill.h:71-80`, `engine/src/hy4flash/metal/hy4_metal_serve.h:271-285`】
- serve の `INFO` 行は stdout のプロトコル出力として、計算後の slot 数を `slots=`、1 slot の計算上のサイズを `slot_mib=` で報告します。追加セットを割り当てると stderr に `[slots] allocated KV set ...` が出ます。【`engine/src/hy4flash/metal/hy4_metal_serve.h:278-285`, `engine/src/hy4flash/metal/hy4_metal_serve.h:302-304`】

## 出力とエラー

オプション値専用の validation error、警告、終了コード分岐は確認できませんでした。parser は `atoi` の結果を記録し、serve の slot 数計算へ進みます。引数を省いた場合も値取得 lambda が次の argv を直接参照し、専用の欠落値エラー処理はありません。欠落時の動作は有効な入力として扱えません。【`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1595`】

serve 起動時は stdout に `INFO ... slots=<eff_slots> slot_mib=<KVセットサイズ>` と `READY <max_context> stop` を出します。初期化失敗時は stdout に `ERR init: ...` を出して終了コード1となりますが、これはこのオプション値専用の失敗経路ではありません。【`engine/src/hy4flash/metal/hy4_metal_serve.h:239-243`, `engine/src/hy4flash/metal/hy4_metal_serve.h:302-304`】

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1494-1497` — `--session-reuse` の初期状態と `--conversation-cache-mib` の既定値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1592-1599` — CLI parser。値を `atoi` で読み込み、専用の範囲検査を行わない。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1654` — `--load-only` の終了位置、serve オプションへの値の引き渡し、slot 数の既定値。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:227-232`, `262-285` — 再利用時の計画設定、最低1を含む有効 slot 数計算、遅延セット割り当て。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:379-396`, `614-618` — 1会話分の KV セット構成とサイズ計算。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:637-659` — cold-expert cache の作業予算、追加 KV 予約の差し引きと下限。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:302-304`, `engine/src/hy4flash/metal/hy4_metal_serve.h:375-404`, `engine/src/hy4flash/metal/hy4_metal_slots.h:35-67` — 起動時の slot 報告、slot 選択と追加割り当て。
- `engine/src/hy4flash/metal/hy4_metal_spill.h:71-80` — spill root の解決規則。
