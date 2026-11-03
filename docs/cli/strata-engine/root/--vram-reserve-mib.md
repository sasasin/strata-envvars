# `--vram-reserve-mib`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、トップレベル引数） |
| オプション | `--vram-reserve-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数を1つ指定 |

## 役割

モデルの重み・セッション・エキスパートキャッシュなどを配置するとき、後続の GPU 作業向けに見積り上残す VRAM 量を指定します。主に `--expert-cache auto` のキャッシュ容量や、明示したキャッシュ容量が他の割当てと共存できるかの判断に影響します。起動例は `strata --pack /path/to/pack --tokens "1,2,3" --vram-reserve-mib 1200` です（エンジン引数の基本形は `src/program/generate.cpp:1011-1017`）。

## 値と既定値

- 既定値は `700` MiB です（`src/program/generate.cpp:792-793`）。
- parser は次の argv 要素を `std::atoi` で整数化し、指定済みフラグを立てます（`src/program/generate.cpp:3293-3298,3448`）。値域の検査はこの parser 分岐にはありません。したがって、整数として解釈できない文字列は `atoi` の規則で `0` になり、数値の後ろに余分な文字がある場合も数値部分が使われます。負数もここでは拒否されません。これらの値を安全な設定値として推奨する意図はありません。
- 値が欠けると `--vram-reserve-mib needs a value` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:3295-3297,3448`）。同じオプションを複数回指定した場合、ループ内で値を上書きするため最後に解析された値が残ります（`src/program/generate.cpp:3293-3298,3448`）。

## 実行時の動作

`--expert-cache auto` のサイズ計算では、この値に加えてプロンプト用バッファ、ドラフトヘッド、パイプライン用メモリ等を空き VRAM から差し引き、残りをキャッシュスロットに回します（`src/program/generate.cpp:7535-7559,7575-7579`）。そのため、他条件が同じなら大きい reserve は自動キャッシュを小さくし、小さい reserve はより多くの VRAM をキャッシュ等に回せる計算になります。レイヤー分割時も各 stage の空き容量計算に使われます。後段 GPU には `--vram-reserve-later-mib` を指定でき、指定がなければこの reserve が使われます（`src/program/generate.cpp:5715-5731`）。

明示指定は `vram_reserve_given` に記録され、reserve を自動で縮めたり置き換えたりする救済経路を抑えます。例として、小さいカードで必要スロット数を満たせない場合の reserve 引下げは未指定時だけ行われ、必要容量を確保できなければ「空き VRAM がない」旨を出します（`src/program/generate.cpp:7620-7644,7705-7725`）。一方、明示した `--expert-cache N` は reserve 等を差し引いた枠を超えるとスロット数を切り詰める警告経路があります（レイヤー分割の場合: `src/program/generate.cpp:7727-7743`）。

## 適用条件と副作用

- Windows HIP ビルドで、GPU が報告する総 VRAM が 15 GiB 以上の場合、自動キャッシュ用 reserve は既定の 700 MiB から 2560 MiB に引き上げられます。ただしこのオプションを明示していれば引上げません。該当分岐は Windows HIP に限られ、他 backend に同じ floor があるとは確認できません（`src/program/generate.cpp:7516-7533`）。
- serve 起動後も、要求開始時に空き VRAM が安全閾値を下回ると stderr に警告し、reserve を増やす案や `--max-context` / `--batch` を下げる案を示します（`src/program/generate.cpp:14825-14838`）。起動 reserve は動的に VRAM を割り当てたり、他プロセスの使用量を制限したりするものではありません。
- `--vram-elastic` を使う serve では、入力行 `VRAM`（引数なし）の目標値として起動時の reserve が参照されます。`VRAM <reserve_mib>` を実行時に指定する形式とは別の操作です（`src/program/generate.cpp:13471-13479`）。
- reserve を大きくすればキャッシュ等に使える見積り容量が小さくなり、スロット数やプロンプト処理の適応に影響します。逆に小さくすると後続割当ての余裕を狭めるため、起動後の警告や GPU メモリ不足につながる可能性があります。実際の空き容量は他プロセスや割当て状況にも依存します。

## 出力とエラー

reserve の値そのものが独立して検証されるエラー経路は parser 内に見当たりません。serve では起動完了時の空き VRAMを表示し、低い場合には警告します（`src/program/generate.cpp:13202-13229`）。自動キャッシュが必要スロット数を作れない場合は、必要スロット数と不足量、空きを作る方法を stderr に出します（`src/program/generate.cpp:7705-7725`）。後続の GPU 割当てが実際に失敗した場合の全エラー経路は、backend・割当て箇所によって異なるため、この調査では網羅していません。

## 根拠

- option の既定値と指定済み状態: `src/program/generate.cpp:792-793`
- 引数の値取得・変換・不足値処理: `src/program/generate.cpp:3293-3298,3448`
- 自動キャッシュ容量と Windows HIP の例外: `src/program/generate.cpp:7516-7559,7575-7579`
- 明示指定時の自動調整抑止と容量不足経路: `src/program/generate.cpp:7620-7644,7705-7743`
- 複数 GPU stage の reserve: `src/program/generate.cpp:5715-5731`
- 起動後の VRAM 表示・serve 警告: `src/program/generate.cpp:13202-13229,14825-14838`
- `--vram-elastic` の `VRAM` コマンドとの関係: `src/program/generate.cpp:13471-13479`

この文書はソース parser と使用箇所を調べたもので、同一 revision の実行バイナリによる `--help` 出力や各 GPU/backend の実行確認は行っていません。
