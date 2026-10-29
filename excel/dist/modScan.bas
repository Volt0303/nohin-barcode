Attribute VB_Name = "modScan"
Option Explicit

' 入荷バーコード読み取り
' バーコードの内容は "注番,納入数"（例: YN34214,10000）。
' 読み取り欄 (shScan!B3) に入力されると、shData に1行追加して保存する。

Private Const INPUT_CELL As String = "B3"
Private Const STATUS_CELL As String = "B5"
Private Const COL_TIME As Long = 1
Private Const COL_CHUBAN As Long = 2
Private Const COL_QTY As Long = 3
Private Const COL_PASSED As Long = 4
Private Const COL_PC As Long = 5
Private Const MAX_QTY_DIGITS As Long = 7

Public Sub SetupInputCell()
    On Error Resume Next
    With shScan.Range(INPUT_CELL).Validation
        .Delete
        .Add Type:=xlValidateInputOnly
        .IMEMode = xlIMEModeDisable
    End With
    On Error GoTo 0
End Sub

Public Sub HandleScan(ByVal Target As Range)
    Dim raw As String, parts() As String, chuban As String, qty As String

    If Target.CountLarge <> 1 Then Exit Sub
    If Target.Address(False, False) <> INPUT_CELL Then Exit Sub
    raw = NormalizeInput(CStr(Target.Value))
    If raw = "" Then Exit Sub

    Application.EnableEvents = False
    On Error GoTo Failed
    Target.Value = ""

    parts = Split(raw, ",")
    If UBound(parts) <> 1 Then
        ShowError "このバーコードは読み取り対象ではありません（" & raw & "）"
        GoTo Finish
    End If
    chuban = parts(0)
    qty = parts(1)
    If Not IsValidChuban(chuban) Or Not IsValidQty(qty) Then
        ShowError "バーコードの内容が正しくありません（" & raw & "）"
        GoTo Finish
    End If

    ' OK/Cancel, not Yes/No: はい(Y)/いいえ(N) have letter shortcuts, so scanning the
    ' next slip ("YN...") into the dialog would press はい. Scanner input is ignored
    ' here and its Enter picks the default button, Cancel.
    If IsDuplicate(chuban, CLng(qty)) Then
        If MsgBox("注番 " & chuban & "・納入数 " & qty & " は既に読み取り済みです。" & vbCrLf & _
                  "もう一度追加する場合は「OK」、追加しない場合は「キャンセル」を押してください。", _
                  vbOKCancel + vbExclamation + vbDefaultButton2, "重複の確認") <> vbOK Then
            ShowStatus "追加を取り消しました（" & chuban & " ／ " & qty & "）", RGB(120, 120, 120)
            GoTo Finish
        End If
    End If

    AppendRow chuban, CLng(qty)
    ThisWorkbook.Save
    ShowStatus "読み取りOK： 注番 " & chuban & " ／ 納入数 " & Format$(CLng(qty), "#,##0") & _
               "（" & Format$(Now, "hh:nn:ss") & "）", RGB(0, 128, 0)

Finish:
    Application.EnableEvents = True
    shScan.Range(INPUT_CELL).Select
    Exit Sub

Failed:
    Application.EnableEvents = True
    ShowError "エラーが発生しました：" & Err.Description
    shScan.Range(INPUT_CELL).Select
End Sub

' Full-width characters (IME on) to half-width, upper case, no spaces.
Private Function NormalizeInput(ByVal s As String) As String
    s = StrConv(s, vbNarrow)
    s = Replace(s, ChrW(&H3001), ",")   ' Japanese comma
    s = Replace(s, ChrW(&HFF64), ",")   ' Japanese comma after vbNarrow
    s = Replace(s, " ", "")
    s = Replace(s, vbTab, "")
    s = Replace(s, vbCr, "")
    s = Replace(s, vbLf, "")
    NormalizeInput = UCase$(s)
End Function

' 1-4 letters followed by 3-10 digits, e.g. YN34214.
Private Function IsValidChuban(ByVal s As String) As Boolean
    Dim i As Long, letters As Long, ch As String
    If Len(s) < 4 Or Len(s) > 14 Then Exit Function
    For i = 1 To Len(s)
        ch = Mid$(s, i, 1)
        If ch Like "[A-Z]" Then
            If i <> letters + 1 Then Exit Function
            letters = letters + 1
        ElseIf Not ch Like "#" Then
            Exit Function
        End If
    Next i
    IsValidChuban = letters >= 1 And letters <= 4 And Len(s) - letters >= 3
End Function

Private Function IsValidQty(ByVal s As String) As Boolean
    Dim i As Long
    If Len(s) < 1 Or Len(s) > MAX_QTY_DIGITS Then Exit Function
    For i = 1 To Len(s)
        If Not Mid$(s, i, 1) Like "#" Then Exit Function
    Next i
    IsValidQty = CLng(s) > 0
End Function

Private Function IsDuplicate(ByVal chuban As String, ByVal qty As Long) As Boolean
    Dim lastRow As Long, r As Long
    lastRow = LastDataRow()
    For r = 2 To lastRow
        If CStr(shData.Cells(r, COL_CHUBAN).Value) = chuban And _
           Val(shData.Cells(r, COL_QTY).Value) = qty Then
            IsDuplicate = True
            Exit Function
        End If
    Next r
End Function

Private Sub AppendRow(ByVal chuban As String, ByVal qty As Long)
    Dim r As Long
    r = LastDataRow() + 1
    With shData
        .Cells(r, COL_TIME).Value = Now
        .Cells(r, COL_TIME).NumberFormat = "yyyy/mm/dd hh:mm:ss"
        .Cells(r, COL_CHUBAN).NumberFormat = "@"
        .Cells(r, COL_CHUBAN).Value = chuban
        .Cells(r, COL_QTY).Value = qty
        .Cells(r, COL_QTY).NumberFormat = "#,##0"
        .Cells(r, COL_PASSED).Value = qty
        .Cells(r, COL_PASSED).NumberFormat = "#,##0"
        .Cells(r, COL_PASSED).Interior.Color = RGB(255, 248, 214)
        .Cells(r, COL_PC).Value = Environ$("COMPUTERNAME")
    End With
End Sub

Private Function LastDataRow() As Long
    LastDataRow = shData.Cells(shData.Rows.Count, COL_TIME).End(xlUp).Row
End Function

Private Sub ShowStatus(ByVal message As String, ByVal fontColor As Long)
    With shScan.Range(STATUS_CELL)
        .Value = message
        .Font.Color = fontColor
        .Font.Bold = True
    End With
End Sub

Private Sub ShowError(ByVal message As String)
    Beep
    ShowStatus "×  " & message, RGB(200, 0, 0)
End Sub
