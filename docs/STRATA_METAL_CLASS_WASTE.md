# `STRATA_METAL_CLASS_WASTE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal エンジンの expert streaming で、レイヤーごとに異なる expert slot サイズをいくつのサイズクラスにまとめるかを調整します。各クラスの slot はそのクラスで最大の expert サイズに揃います。このため、クラスが少ないほどクラスごとに確保する最低 slot 数に伴うメモリを抑えられますが、小さい expert の slot に余分な領域が生じます。

この値は `ExpertStream::open()` のクラス分けで使われます。通常のモデル常駐経路では参照されません。

## 値と判定

`std::getenv()` で取得した値を `std::atof()` で `double` に変換します。環境変数が未設定なら `0.15` です。空文字を含め、設定されていれば変換結果がそのまま使われます。

| 設定 | `waste` の値 | クラス分けへの影響 |
|---|---:|---|
| 未設定 | `0.15` | 既定の許容 waste 率でサイズをまとめる |
| 数値文字列 | `atof` の変換結果 | レイヤー slot サイズからクラス境界を計算する |
| 空文字、数値に変換できない文字列 | `0` | 異なる slot サイズを別クラスにする |

文字列全体の消費確認、エラー報告、値域の clamp はありません。`atof` が数値の接頭部分を変換できる場合はその値が使われ、たとえば `0.2tail` は `0.2` として扱われます。数値変換できない文字列は `0` になります。負数や `1` より大きい値も拒否されません。

実装は expert slot のページ数を重複除去して大きい順に走査し、直前に作ったクラスの最大ページ数を `top`、今回のサイズを `size` として、`size < (1 - waste) * top` のときだけ新しいクラスを追加します。この比較は厳密な `<` です。そのため `waste=0` では異なるサイズが別クラスになり、率を大きくするとクラスをまとめやすくなります。境界外の値も同じ式に渡るため、通常想定の「最大 waste 率」と異なる分類結果になり得ます。

## 有効になる条件

- Metal エンジンの `Window::init()` が expert streaming を選び、`ExpertStream::open()` まで進む必要があります。streaming はモデルが常駐 footprint に収まらない場合に選ばれ、`STRATA_METAL_STREAM=1` ならサイズ条件にかかわらず選択、`STRATA_METAL_STREAM=0` なら選択されません。
- 対象経路は Metal エンジンです。`docs/MAC.md` は Metal エンジンを Mac 向けとして案内しています。
- 値は `ExpertStream::open()` の呼び出し中に読み取られます。関数を呼ぶたびに環境から取得するため、このコードにはプロセス内 static cache はありません。
- CLI 引数や設定ファイルによる同名値の上書きは、このコード経路にはありません。

## 実行時の詳細

`ExpertStream::open()` は各レイヤーの gate/up/down expert サイズを足し、16 KiB ページ単位に切り上げます。異なるページ数を大きい順に処理し、上記の条件に合うサイズを新しいクラスの先頭サイズとして記録します。その後、各レイヤーを「slot を収容できる最小クラス」に割り当てます。

`make_arena()` はクラスごとに `min_slots` 個の slot を最低限確保し、その後プロファイル順の expert を予算内で追加します。各 slot の arena サイズは所属クラスのページ数に基づくため、クラスの数と分類結果が arena のサイズ、クラス数、利用可能な slot 数に影響します。起動時の stderr には、最終的な arena サイズ、slot 数、size class 数などが `strata metal stream: expert arena ...` として出力されます。

この変数自体の値を表示するログや、無効値を知らせる警告はありません。異常に大きい／小さい値を設定したときの具体的な arena サイズや起動可否は、モデルの各レイヤーのサイズと他の arena 条件にも依存し、この値だけから一意には決まりません。

## 根拠

- `metal/src/engine/stream.cpp:27-30`: 共通の整数用 helper（本変数はこれを使わず `atof` を直接使用）。
- `metal/src/engine/stream.cpp:122-147`: 既定値、変換、サイズクラス境界の式、各レイヤーのクラス割り当て。
- `metal/src/engine/stream.cpp:398-415,420-423,538-541`: クラスごとの最低 slot 数、slot のページ数による arena サイズ、起動ログ。
- `metal/src/engine/window.cpp:425-435`: `ExpertStream::wanted()` が true のときだけ streaming object を開く経路。
- `metal/src/engine/stream.cpp:33-48`: `STRATA_METAL_STREAM` による強制 ON/OFF と既定の footprint 判定。
- `docs/MAC.md:181,194-198`: Metal エンジンの案内と streaming 関連スイッチの説明。`STRATA_METAL_CLASS_WASTE` の個別説明や測定値は同資料にはありません。
