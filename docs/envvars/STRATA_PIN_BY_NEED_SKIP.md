# `STRATA_PIN_BY_NEED_SKIP`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_PIN_BY_NEED` による expert arena の pin 優先順位を調整します。expert profile の先頭から何組を「GPU キャッシュに入る見込み」と数えるかを指定し、その組は非常駐見込みの組より後に pin します。値を指定しても単独では機能せず、`STRATA_PIN_BY_NEED` が有効な場合に限り参照されます。

ここでの「skip」は pin 対象から完全に除外する意味ではありません。非常駐見込みの組を先に登録し、上限に余裕があれば skip 数に含めた組も後から登録する優先順位です。

## 値と判定

変数は `getenv()` で起動時に読み、空でない場合は `std::atoll()` で変換します。変換結果は負値を 0 にし、profile の組数を上限として切り詰めます。文字列全体の妥当性は検査しません。

| 値 | 扱い |
|---|---|
| 未設定または空文字 | 値指定なし。GPU キャッシュ容量から skip 数を見積もる |
| `12` | profile の先頭12組を常駐見込みとして扱う（profile が短ければ全組数まで） |
| `-2` | 0 に丸める |
| `abc` など数字で始まらない文字列 | `atoll` の変換結果 0 を使う |
| `12tail` | 先頭の数値部分 12 を使う |

`atoll` のため、先頭の空白と符号は数値変換の規則に従い、末尾の文字列は数値部分の後で無視されます。数値として表現できない極端な桁数の動作は、このコードで検査・処理していません。

根拠: `src/program/generate.cpp:4938-4942`。

## 有効になる条件

次の条件が必要です。

- `STRATA_PIN_BY_NEED` が設定され、空文字でなく、先頭文字が `0` ではない。
- `--mmap-experts` を使わず、expert arena を使う経路である。
- `--expert-profile` で読み込んだ profile が空でない。
- 単一 GPU で、layer split / peer GPU がなく、他 GPU の helper cache もない。

条件を満たさない場合、pin-by-need 自体が無効になり、従来の prefix pinning が残ります。この場合 `STRATA_PIN_BY_NEED_SKIP` は読み取られません。pin-by-need が有効でも、skip 数を指定した後に pin できる範囲は `STRATA_ARENA_PIN_GIB` の上限や driver の登録拒否に制約されます。Windows では `STRATA_ARENA_PIN_GIB` が未指定ならこの経路の登録上限は既定29 GiBです。

根拠: `src/program/generate.cpp:4821-4838,4929-4937`; `src/core/pinned.cu:513-527,548-553`。

## 実行時の詳細

engine の起動時、`--expert-profile` は `read_expert_profile()` で読み込まれ、rank 順の組リストになります。pin-by-need 有効時にこのリストを参照し、明示値がなければ GPU cache の容量を見積もって skip 数を決めます。`--expert-cache N` が正なら最大 blob サイズ×N を容量とし、それ以外では GPU の空き容量から VRAM reserve、prefill、MTP、pipeline の予約分を引き、98% に縮めた範囲へ rank 順に blob を加算します。

skip 数 `R` が決まると、profile の rank `R` 以降の組と profile にない全組を先に候補にし、profile の先頭 `R` 組をその後ろに置きます。arena source にこの順位を渡して開くため、実行中のリクエスト単位ではなく arena の登録時に適用されます。コード上、環境変数を再読するループはありません。

arena source は各 expert blob がページ境界から始まる padded layout を作り、優先順位を保って隣接 blob を登録範囲にまとめます。登録は候補順に行われ、cap を超える次の範囲で停止し、driver が範囲を拒否した場合もそれ以降の登録を停止します。したがって skip に含めた組も cap に余裕があれば pin され得ますが、候補の後ろにあるため優先度は低くなります。pin 結果は `pinned()` / `device_alias()` / `pcie_layer()` に反映され、生成時 stderr には常駐見込み数・候補数、および登録範囲数・pin 量が出ます。

未設定時の容量見積もりと明示値の分岐、候補順、ログ: `src/program/generate.cpp:4938-4986`。登録範囲の構築と優先順位: `include/strata/core/expert_source.hpp:952-962`; `src/core/expert_source.cpp:4614-4643`。cap と登録停止: `src/core/pinned.cu:513-553`。結果の参照: `src/core/expert_source.cpp:4865-4884`。

## 文書との照合

`docs/DETAILS.md:188-194` は `STRATA_PIN_BY_NEED` の仕組み、pin 上限、記載された RTX 3090 + Ryzen 5 5600X の測定を説明していますが、`STRATA_PIN_BY_NEED_SKIP` の値の解釈や個別測定は記載していません。上記の skip の意味はソースコードから確認したものです。skip 値による性能や適切な数値は資料から確認できないため、ここでは性能効果を断定しません。
